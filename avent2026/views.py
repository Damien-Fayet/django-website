from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import robot, scene, scoring
from .models import Attempt, Hint, HintReveal, Puzzle


def _locked_response(request, day, puzzle=None):
    target = scoring.unlock_date(puzzle) if puzzle else None
    return render(request, "avent2026/locked.html", {"day": day, "unlock_date": target}, status=403)


@login_required
def home(request):
    """Scène d'accueil : deux sentiers (énigmes, devinettes) de 24 étapes, jouables dans n'importe quel ordre."""
    puzzles = {(p.kind, p.day): p for p in Puzzle.objects.only("id", "kind", "day", "title", "unlock_date")}
    solved_ids = set(Attempt.objects.filter(user=request.user, solved_at__isnull=False)
                     .values_list("puzzle_id", flat=True))

    nodes = []
    for day in range(1, 25):
        for kind in scene.KINDS:
            puzzle = puzzles.get((kind, day))
            unlocked = scoring.is_unlocked(puzzle or day, request.user)
            if not unlocked:
                state = "locked"
            elif puzzle is None:
                state = "empty"
            elif puzzle.id in solved_ids:
                state = "done"
            else:
                state = "open"
            x, y = scene.LANDSCAPE[(kind, day)]
            px, py = scene.PORTRAIT[(kind, day)]
            nodes.append({
                "kind": kind, "day": day, "state": state, "x": x, "y": y, "px": px, "py": py,
                "puzzle": puzzle if state in ("open", "done") else None,
                "kind_label": "Énigme" if kind == Puzzle.ENIGME else "Devinette",
            })
    scores = _user_scores(request.user)
    unlocked_days = {n["day"] for n in nodes if n["state"] != "locked"}
    zones = scene.zones_context()
    for z in zones:
        z["lit"] = any(d in unlocked_days for d in z["days"])
    # Le robot se tient sur le dernier puzzle résolu (n'importe quelle piste), sinon au départ de l'énigme du jour 1.
    last = (Attempt.objects.filter(user=request.user, solved_at__isnull=False)
            .order_by("-solved_at").values_list("puzzle__kind", "puzzle__day").first()) or (Puzzle.ENIGME, 1)
    robot_node = next(n for n in nodes if (n["kind"], n["day"]) == last)
    show_prologue = not request.session.get("avent2026_prologue_seen")
    request.session["avent2026_prologue_seen"] = True
    return render(request, "avent2026/home.html", {
        "nodes": nodes, "scores": scores, "zones": zones, "robot": robot.robot_state(scores["total"]),
        "robot_node": robot_node, "prologue": robot.PROLOGUE if show_prologue else "",
        "epilogue": robot.EPILOGUE if _finished(request.user) else "",
        "days_total": 24,
    })


def old_day_redirect(request, day):
    """Ancienne page « Jour N », supprimée avec les deux pistes : on renvoie vers la scène."""
    return redirect("avent2026:home")


def _finished(user):
    """Épilogue : tous les puzzles publiés du jour 24 (les deux pistes) sont résolus."""
    day24 = list(Puzzle.objects.filter(day=24).values_list("id", flat=True))
    if not day24:
        return False
    solved = Attempt.objects.filter(user=user, puzzle_id__in=day24, solved_at__isnull=False).count()
    return solved == len(day24)


def _puzzle_context(request, puzzle):
    attempt = Attempt.objects.filter(user=request.user, puzzle=puzzle).first()
    hints = list(puzzle.hints.all())
    revealed_ids = set(HintReveal.objects.filter(user=request.user, hint__puzzle=puzzle).values_list("hint_id", flat=True))
    for h in hints:
        h.revealed = h.id in revealed_ids
        h.display_cost = scoring.hint_cost(h)
    revealed = [h for h in hints if h.revealed]
    next_hint = next((h for h in hints if not h.revealed), None)
    errors = attempt.errors if attempt else 0
    return {
        "puzzle": puzzle, "attempt": attempt, "solved": bool(attempt and attempt.solved),
        "revealed_hints": revealed, "next_hint": next_hint, "hint_count": len(hints),
        "errors": errors, "max_points": scoring.puzzle_base_points(puzzle),
        "current_points": scoring.compute_points(puzzle, errors, revealed),
        "other": _other_track(request, puzzle),
        # Le fragment d'histoire n'est envoyé au template qu'une fois le puzzle résolu.
        "story": puzzle.story if attempt and attempt.solved else "",
    }


def _other_track(request, puzzle):
    """L'autre puzzle du même jour (l'autre piste), avec son état, pour le lien « même jour »."""
    other = Puzzle.objects.filter(day=puzzle.day).exclude(pk=puzzle.pk).first()
    if other is None:
        return None
    other.unlocked = scoring.is_unlocked(other, request.user)
    other.done = Attempt.objects.filter(user=request.user, puzzle=other, solved_at__isnull=False).exists()
    return other


@login_required
def puzzle_view(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    if not scoring.is_unlocked(puzzle, request.user):
        return _locked_response(request, puzzle.day, puzzle)
    return render(request, "avent2026/puzzle.html", _puzzle_context(request, puzzle))


@login_required
@require_POST
def answer(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    if not scoring.is_unlocked(puzzle, request.user):
        return _locked_response(request, puzzle.day, puzzle)
    with transaction.atomic():
        attempt, _ = Attempt.objects.select_for_update().get_or_create(user=request.user, puzzle=puzzle)
        if attempt.solved:
            messages.info(request, "Tu as déjà résolu celle-ci.")
        elif scoring.is_correct(puzzle, request.POST.get("answer", "")):
            revealed = Hint.objects.filter(puzzle=puzzle, reveals__user=request.user)
            attempt.points = scoring.compute_points(puzzle, attempt.errors, list(revealed))
            attempt.solved_at = timezone.now()
            attempt.save()
            messages.success(request, f"Bravo ! +{attempt.points} points.")
        else:
            attempt.errors += 1
            attempt.save(update_fields=["errors"])
            messages.error(request, "Ce n'est pas ça, essaie encore.")
    return redirect("avent2026:puzzle", puzzle_id=puzzle.id)


@login_required
@require_POST
def reveal_hint(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    if not scoring.is_unlocked(puzzle, request.user):
        return _locked_response(request, puzzle.day, puzzle)
    if Attempt.objects.filter(user=request.user, puzzle=puzzle, solved_at__isnull=False).exists():
        return redirect("avent2026:puzzle", puzzle_id=puzzle.id)
    # Indices révélés dans l'ordre : on donne toujours le prochain non révélé.
    hint = puzzle.hints.exclude(reveals__user=request.user).order_by("number").first()
    if hint:
        HintReveal.objects.get_or_create(user=request.user, hint=hint)
        messages.info(request, f"Indice révélé (−{scoring.hint_cost(hint)} points si tu trouves).")
    return redirect("avent2026:puzzle", puzzle_id=puzzle.id)


def _user_scores(user):
    """Points et nombre de puzzles résolus par piste, plus le total (l'énergie du robot)."""
    rows = (Attempt.objects.filter(user=user, solved_at__isnull=False)
            .values("puzzle__kind").annotate(total=Sum("points"), solved=Count("id")))
    by_kind = {r["puzzle__kind"]: r for r in rows}
    scores = {"total": sum(r["total"] for r in rows)}
    for kind in (Puzzle.ENIGME, Puzzle.DEVINETTE):
        scores[kind] = by_kind[kind]["total"] if kind in by_kind else 0
        scores[kind + "_solved"] = by_kind[kind]["solved"] if kind in by_kind else 0
    return scores


@login_required
def leaderboard(request):
    rows = (Attempt.objects.filter(solved_at__isnull=False)
            .values("user__username", "puzzle__kind").annotate(total=Sum("points"), solved=Count("id")))
    board = {Puzzle.ENIGME: [], Puzzle.DEVINETTE: [], "total": defaultdict(int)}
    for r in rows:
        board[r["puzzle__kind"]].append({"name": r["user__username"], "points": r["total"], "solved": r["solved"]})
        board["total"][r["user__username"]] += r["total"]
    for kind in (Puzzle.ENIGME, Puzzle.DEVINETTE):
        board[kind].sort(key=lambda r: (-r["points"], r["name"]))
    total = sorted(({"name": n, "points": p} for n, p in board["total"].items()), key=lambda r: (-r["points"], r["name"]))
    return render(request, "avent2026/leaderboard.html", {
        "enigmes": board[Puzzle.ENIGME], "devinettes": board[Puzzle.DEVINETTE], "total": total,
        "me": request.user.username,
    })


@login_required
def journal(request):
    """Journal de bord : prologue et fragments d'histoire des puzzles déjà résolus."""
    solved = (Attempt.objects.filter(user=request.user, solved_at__isnull=False).exclude(puzzle__story="")
              .select_related("puzzle").order_by("puzzle__day", "-puzzle__kind"))
    scores = _user_scores(request.user)
    return render(request, "avent2026/journal.html", {
        "entries": [a.puzzle for a in solved], "prologue": robot.PROLOGUE,
        "epilogue": robot.EPILOGUE if _finished(request.user) else "",
        "robot": robot.robot_state(scores["total"]),
    })
