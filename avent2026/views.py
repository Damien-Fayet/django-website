from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import scoring, village
from .models import Attempt, Hint, HintReveal, Puzzle


def _locked_response(request, day, puzzle=None):
    target = scoring.unlock_date(puzzle) if puzzle else None
    return render(request, "avent2026/locked.html", {"day": day, "unlock_date": target}, status=403)


@login_required
def home(request):
    """Accueil : les deux villages (énigmes, devinettes), chacun avec 24 lumières à rallumer, une par jour."""
    puzzles = {(p.kind, p.day): p for p in Puzzle.objects.only("id", "kind", "day", "title", "unlock_date")}
    solved_ids = set(Attempt.objects.filter(user=request.user, solved_at__isnull=False)
                     .values_list("puzzle_id", flat=True))

    villages = []
    for kind in village.KINDS:
        info = village.village_info(kind)
        lights = []
        for day in range(1, village.DAYS + 1):
            puzzle = puzzles.get((kind, day))
            if not scoring.is_unlocked(puzzle or day, request.user):
                state = "locked"
            elif puzzle is None:
                state = "empty"
            elif puzzle.id in solved_ids:
                state = "done"
            else:
                state = "open"
            x, y = village.light_position(kind, day)
            lights.append({
                "day": day, "state": state, "x": x, "y": y,
                "puzzle": puzzle if state in ("open", "done") else None,
            })
        lit = sum(1 for light in lights if light["state"] == "done")
        entry = {**info, "lights": lights, "lit": lit, "total": village.DAYS}
        if kind in village.CARTES:
            entry["image"] = None
            entry["carte"] = _carte(request, kind, lit)
        else:
            entry["image"] = village.image_path(kind)
        villages.append(entry)
    scores = _user_scores(request.user)
    finale = _finished(request.user)
    show_prologue = not request.session.get("avent2026_prologue_seen")
    if show_prologue:  # n'écrire la session qu'une fois : sinon un UPDATE par visite
        request.session["avent2026_prologue_seen"] = True
    return render(request, "avent2026/home.html", {
        "villages": villages, "scores": scores,
        "village": village.village_state(scores["lit"]), "finale": finale,
        "prologue": village.PROLOGUE if show_prologue else "",
        "epilogue": village.EPILOGUE if finale else "",
    })


def _carte(request, kind, step):
    """Image « étape `step` » du village dessiné étape par étape, et l'étape vue à la visite précédente.

    `previous` n'est donné que si des puzzles ont été résolus depuis : le template fait alors apparaître
    en fondu la nouvelle image par-dessus l'ancienne. L'étape n'est enregistrée comme « vue » qu'au moment où
    le navigateur confirme l'avoir affichée (`carte_seen`) : un rendu perdu ou préchargé ne consomme pas le fondu.
    """
    key = f"avent2026_carte_{kind}"
    seen = request.session.get(key)
    if not isinstance(seen, int) or seen > step:  # première visite, ou étape en recul : rien à animer
        request.session[key] = seen = step
    previous = seen if seen < step else None
    return {
        "step": step, "image": village.carte_image_path(kind, step),
        "previous": village.carte_image_path(kind, previous) if previous is not None else None,
        "missing": f"static/avent2026/img/{village.CARTES[kind][0]}/{village.CARTES[kind][1].format(step=step)}.webp",
    }


@login_required
@require_POST
def carte_seen(request, kind):
    """Le navigateur a affiché la nouvelle étape de la carte : le fondu ne sera plus rejoué."""
    if kind not in village.CARTES:
        raise Http404
    try:
        step = int(request.POST.get("step", ""))
    except ValueError:
        return HttpResponseBadRequest()
    if not 0 <= step <= village.DAYS:
        return HttpResponseBadRequest()
    key = f"avent2026_carte_{kind}"
    seen = request.session.get(key)
    request.session[key] = max(step, seen) if isinstance(seen, int) else step
    return HttpResponse(status=204)


@login_required
def calibration(request, kind):
    """Page réservée au staff : cliquer sur l'illustration pour relever la position des 24 lumières."""
    if not request.user.is_staff or kind not in village.KINDS or kind in village.CARTES:
        raise Http404
    return render(request, "avent2026/calibration.html", {
        **village.village_info(kind), "image": village.image_path(kind),
        # Les deux villages : le texte à coller dans lights.json contient les deux listes.
        "all_lights": {k: [list(village.light_position(k, d)) for d in range(1, village.DAYS + 1)]
                       for k in village.KINDS},
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
    """Points et nombre de puzzles résolus par piste, plus le total (les points du classement)."""
    rows = (Attempt.objects.filter(user=user, solved_at__isnull=False)
            .values("puzzle__kind").annotate(total=Sum("points"), solved=Count("id")))
    by_kind = {r["puzzle__kind"]: r for r in rows}
    scores = {"total": sum(r["total"] for r in rows)}
    for kind in (Puzzle.ENIGME, Puzzle.DEVINETTE):
        scores[kind] = by_kind[kind]["total"] if kind in by_kind else 0
        scores[kind + "_solved"] = by_kind[kind]["solved"] if kind in by_kind else 0
    scores["lit"] = scores["enigme_solved"] + scores["devinette_solved"]  # lumières allumées dans le village
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
    """Journal de bord : prologue et fragments d'histoire des lumières déjà allumées."""
    solved = (Attempt.objects.filter(user=request.user, solved_at__isnull=False).exclude(puzzle__story="")
              .select_related("puzzle").order_by("puzzle__day", "-puzzle__kind"))
    scores = _user_scores(request.user)
    return render(request, "avent2026/journal.html", {
        "entries": [a.puzzle for a in solved], "prologue": village.PROLOGUE,
        "epilogue": village.EPILOGUE if _finished(request.user) else "",
        "village": village.village_state(scores["lit"]),
    })
