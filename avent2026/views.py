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
    """Scène d'accueil : 24 points d'intérêt, jouables dans n'importe quel ordre une fois débloqués."""
    content = defaultdict(int)  # jour -> nombre de puzzles publiés
    for day, total in Puzzle.objects.values_list("day").annotate(n=Count("id")):
        content[day] = total
    solved = defaultdict(int)
    for day in Attempt.objects.filter(user=request.user, solved_at__isnull=False).values_list("puzzle__day", flat=True):
        solved[day] += 1

    nodes = []
    for day in range(1, 25):
        if not scoring.is_unlocked(day, request.user):
            state = "locked"
        elif content[day] and solved[day] >= content[day]:
            state = "done"
        elif not content[day]:
            state = "empty"
        else:
            state = "open"
        nodes.append({
            "day": day, "state": state, "solved": solved[day], "total": content[day],
            "x": scene.LANDSCAPE[day][0], "y": scene.LANDSCAPE[day][1],
            "px": scene.PORTRAIT[day][0], "py": scene.PORTRAIT[day][1],
        })
    scores = _user_scores(request.user)
    unlocked_days = {n["day"] for n in nodes if n["state"] != "locked"}
    zones = scene.zones_context()
    for z in zones:
        z["lit"] = any(d in unlocked_days for d in z["days"])
    last_day = (Attempt.objects.filter(user=request.user, solved_at__isnull=False)
                .order_by("-solved_at").values_list("puzzle__day", flat=True).first()) or 1
    robot_node = next(n for n in nodes if n["day"] == last_day)
    show_prologue = not request.session.get("avent2026_prologue_seen")
    request.session["avent2026_prologue_seen"] = True
    return render(request, "avent2026/home.html", {
        "nodes": nodes, "scores": scores, "zones": zones, "robot": robot.robot_state(scores["total"]),
        "robot_node": robot_node, "prologue": robot.PROLOGUE if show_prologue else "",
        "epilogue": robot.EPILOGUE if _finished(request.user) else "",
    })


@login_required
def day_view(request, day):
    if not 1 <= day <= 24:
        return redirect("avent2026:home")
    if not scoring.is_unlocked(day, request.user):
        return _locked_response(request, day)
    puzzles = list(Puzzle.objects.filter(day=day))
    done_ids = set(Attempt.objects.filter(user=request.user, puzzle__in=puzzles, solved_at__isnull=False)
                   .values_list("puzzle_id", flat=True))
    for p in puzzles:
        p.done = p.id in done_ids
        p.max_points = scoring.puzzle_base_points(p)
    return render(request, "avent2026/day.html", {
        "day": day,
        "enigmes": [p for p in puzzles if p.kind == Puzzle.ENIGME],
        "devinettes": [p for p in puzzles if p.kind == Puzzle.DEVINETTE],
    })


def _finished(user):
    return Attempt.objects.filter(user=user, puzzle__day=24, solved_at__isnull=False).exists()


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
        "siblings": Puzzle.objects.filter(day=puzzle.day, kind=puzzle.kind),
        # Le fragment d'histoire n'est envoyé au template qu'une fois le puzzle résolu.
        "story": puzzle.story if attempt and attempt.solved else "",
    }


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
    rows = Attempt.objects.filter(user=user, solved_at__isnull=False).values("puzzle__kind").annotate(total=Sum("points"))
    scores = {r["puzzle__kind"]: r["total"] for r in rows}
    return {"enigme": scores.get("enigme", 0), "devinette": scores.get("devinette", 0),
            "total": sum(scores.values())}


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
              .select_related("puzzle").order_by("puzzle__day", "puzzle__kind", "puzzle__difficulty"))
    scores = _user_scores(request.user)
    return render(request, "avent2026/journal.html", {
        "entries": [a.puzzle for a in solved], "prologue": robot.PROLOGUE,
        "epilogue": robot.EPILOGUE if _finished(request.user) else "",
        "robot": robot.robot_state(scores["total"]),
    })
