from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import competition, scoring, village
from .models import Attempt, Hint, HintReveal, Puzzle


def _locked_response(request, day, puzzle=None):
    target = scoring.unlock_date(puzzle) if puzzle else None
    hour = scoring.RELEASE_HOUR[puzzle.kind] if puzzle else None
    return render(request, "avent2026/locked.html", {"day": day, "unlock_date": target, "hour": hour}, status=403)


@login_required
def home(request):
    """Accueil : les deux cartes (cellule du Père Noël pour les énigmes, village pour les devinettes) et la progression."""
    puzzles = {(p.kind, p.day): p for p in Puzzle.objects.only("id", "kind", "day", "title", "unlock_date")}
    solved_ids = set(Attempt.objects.filter(user=request.user, solved_at__isnull=False)
                     .values_list("puzzle_id", flat=True))

    cartes = []
    for kind in village.KINDS:
        info = village.CARTES[kind]
        steps = []
        for number, day in enumerate(info.days, start=1):
            puzzle = puzzles.get((kind, day))
            if not (scoring.is_unlocked(puzzle, request.user) if puzzle
                    else scoring.is_day_unlocked(kind, day, request.user)):
                state = "locked"
            elif puzzle is None:
                state = "empty"
            elif puzzle.id in solved_ids:
                state = "done"
            else:
                state = "open"
            steps.append({
                "number": number, "day": day, "state": state,
                "date": scoring.unlock_date(puzzle) if puzzle else date(scoring.YEAR, 12, day),
                "puzzle": puzzle if state in ("open", "done") else None,
            })
        solved = sum(1 for step in steps if step["state"] == "done")
        cartes.append({
            "kind": kind, **info._asdict(), "hour": scoring.RELEASE_HOUR[kind], "steps": steps, "solved": solved, "total": len(info.days),
            "counter": village.counter(kind, solved), "carte": _carte(request, kind, solved),
        })
    scores = _user_scores(request.user)
    finale = _finished(request.user)
    show_prologue = not request.session.get("avent2026_prologue_seen")
    if show_prologue:  # n'écrire la session qu'une fois : sinon un UPDATE par visite
        request.session["avent2026_prologue_seen"] = True
    return render(request, "avent2026/home.html", {
        "cartes": cartes, "scores": scores,
        "village": village.village_state(scores["lit"]), "finale": finale,
        "prologue": village.PROLOGUE if show_prologue else "",
        "epilogue": village.EPILOGUE if finale else "",
    })


def _carte(request, kind, step):
    """Image « étape `step` » de la carte de la piste, et l'étape vue à la visite précédente.

    `previous` n'est donné que si des puzzles ont été résolus depuis : le template fait alors apparaître
    en fondu la nouvelle image par-dessus l'ancienne. L'étape n'est enregistrée comme « vue » qu'au moment où
    le navigateur confirme l'avoir affichée (`carte_seen`) : un rendu perdu ou préchargé ne consomme pas le fondu.
    """
    key = f"avent2026_carte_{kind}"
    seen = request.session.get(key)
    if not isinstance(seen, int) or seen > step:  # première visite, ou étape en recul : rien à animer
        request.session[key] = seen = step
    previous = seen if seen < step else None
    carte = village.CARTES[kind]
    return {
        "step": step, "image": village.carte_image_path(kind, step),
        "previous": village.carte_image_path(kind, previous) if previous is not None else None,
        "missing": f"static/avent2026/img/{carte.folder}/{carte.pattern.format(step=step)}.webp",
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
    if not 0 <= step <= len(village.CARTES[kind].days):
        return HttpResponseBadRequest()
    key = f"avent2026_carte_{kind}"
    seen = request.session.get(key)
    request.session[key] = max(step, seen) if isinstance(seen, int) else step
    return HttpResponse(status=204)


def old_day_redirect(request, day):
    """Ancienne page « Jour N », supprimée avec les deux pistes : on renvoie vers la scène."""
    return redirect("avent2026:home")


def _finished(user):
    """Épilogue : tous les derniers puzzles publiés (un par piste : devinette du 24, énigme du 23) sont résolus."""
    finals = Q()
    for kind, day in village.FINAL_DAYS.items():
        finals |= Q(kind=kind, day=day)
    final_ids = list(Puzzle.objects.filter(finals).values_list("id", flat=True))
    if not final_ids:
        return False
    solved = Attempt.objects.filter(user=user, puzzle_id__in=final_ids, solved_at__isnull=False).count()
    return solved == len(final_ids)


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
    solved = bool(attempt and attempt.solved)
    # Course (énigmes) : bonus obtenus une fois résolue, sinon bonus en jeu si on résolvait maintenant.
    competitive = puzzle.kind in scoring.BONUS_KINDS
    if solved:
        rank = attempt.rank
    else:
        rank = None if request.user.is_staff else competition.next_rank(puzzle)
    days = village.CARTES[puzzle.kind].days
    return {
        "puzzle": puzzle, "attempt": attempt, "solved": solved,
        "revealed_hints": revealed, "next_hint": next_hint, "hint_count": len(hints),
        "errors": errors, "max_points": scoring.puzzle_base_points(puzzle),
        "current_points": scoring.compute_points(puzzle, errors, revealed, rank),
        "competitive": competitive,
        "bonuses": scoring.bonuses(puzzle, rank, errors, revealed) if competitive else [],
        "podium": competition.podium(puzzle) if competitive else [],
        "podium_open": competition.next_rank(puzzle) <= len(scoring.PODIUM_BONUS) if competitive else False,
        "step": days.index(puzzle.day) + 1 if puzzle.day in days else None, "steps": len(days),
        "date": scoring.unlock_date(puzzle), "hour": scoring.RELEASE_HOUR[puzzle.kind],
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
            revealed = list(Hint.objects.filter(puzzle=puzzle, reveals__user=request.user))
            # Écrire la résolution avant de compter les précédentes : l'écriture prend le verrou de SQLite, donc
            # deux résolutions simultanées ne reçoivent pas la même place.
            attempt.solved_at = timezone.now()
            attempt.points = scoring.compute_points(puzzle, attempt.errors, revealed)
            attempt.save()
            if puzzle.kind in scoring.BONUS_KINDS:
                attempt.rank = competition.rank_of(attempt)
                attempt.points = scoring.compute_points(puzzle, attempt.errors, revealed, attempt.rank)
                attempt.save(update_fields=["rank", "points"])
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
        lost = " et le bonus « sans indice »" if puzzle.kind in scoring.BONUS_KINDS else ""
        messages.info(request, f"Indice révélé (−{scoring.hint_cost(hint)} points{lost} si tu trouves).")
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
    scores["lit"] = scores["enigme_solved"] + scores["devinette_solved"]  # étapes franchies (sur village.TOTAL)
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
        "me": request.user.username, "verrous": competition.verrous(), "titles": competition.titles(),
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
