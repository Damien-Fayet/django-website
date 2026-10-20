from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.utils import client_ip

from . import competition, scoring, suivi, village
from .models import Attempt, Hint, HintReveal, Puzzle, Submission


def _step_of(puzzle):
    """Rang du puzzle dans sa piste (1 pour le premier verrou ou le premier jour) et nombre d'étapes de la piste."""
    days = village.CARTES[puzzle.kind].days
    return (days.index(puzzle.day) + 1 if puzzle.day in days else None), len(days)


def _locked_response(request, day, puzzle=None):
    ctx = {"day": day, "unlock_date": None, "hour": None}
    if puzzle:
        step, steps = _step_of(puzzle)
        # Le titre du puzzle n'est volontairement pas transmis : il révélerait le contenu avant l'heure.
        ctx.update(unlock_date=scoring.unlock_date(puzzle), hour=scoring.RELEASE_HOUR[puzzle.kind],
                   unlock_iso=scoring.unlock_at(puzzle).isoformat(), kind=puzzle.kind, step=step, steps=steps)
    return render(request, "avent2026/locked.html", ctx, status=403)


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
                "unlock": scoring.unlock_at(puzzle) if puzzle else scoring.release_at(kind, day),
            })
        solved = sum(1 for step in steps if step["state"] == "done")
        cartes.append({
            "kind": kind, **info._asdict(), "hour": scoring.RELEASE_HOUR[kind], "steps": steps, "solved": solved, "total": len(info.days),
            "counter": village.counter(kind, solved), "carte": _carte(request, kind, solved),
        })
    to_play, next_unlock = _to_play(cartes)
    scores = _user_scores(request.user)
    finale = _finished(request.user)
    show_prologue = not request.session.get("avent2026_prologue_seen")
    if show_prologue:  # n'écrire la session qu'une fois : sinon un UPDATE par visite
        request.session["avent2026_prologue_seen"] = True
    return render(request, "avent2026/home.html", {
        "cartes": cartes, "scores": scores, "to_play": to_play[:TO_PLAY_SHOWN],
        "to_play_more": max(0, len(to_play) - TO_PLAY_SHOWN), "next_unlock": next_unlock,
        "has_empty": any(step["state"] == "empty" for c in cartes for step in c["steps"]),
        "village": village.village_state(scores["lit"]), "finale": finale,
        "prologue": village.PROLOGUE if show_prologue else "",
        "epilogue": village.EPILOGUE if finale else "",
    })


TO_PLAY_SHOWN = 6  # le staff voit tout débloqué : on ne liste pas les 32 puzzles


def _to_play(cartes):
    """Puzzles ouverts et pas encore résolus (les plus anciens d'abord), et le prochain déblocage.

    `next_unlock` : la prochaine étape encore verrouillée (date et heure de Paris), ou None si tout est sorti.
    """
    to_play, locked = [], []
    for c in cartes:
        for step in c["steps"]:
            label = f"{c['step']} {step['number'] if c['dated'] else step['day']}"
            if step["state"] == "open":
                to_play.append({"kind": c["kind"], "track": c["name"], "label": label, "puzzle": step["puzzle"],
                                "date": step["date"], "unlock": step["unlock"]})
            elif step["state"] == "locked":
                locked.append({"track": c["name"], "label": label, "date": step["date"], "hour": c["hour"],
                               "unlock": step["unlock"]})
    to_play.sort(key=lambda item: item["unlock"])
    return to_play, min(locked, key=lambda item: item["unlock"], default=None)


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
    step, steps = _step_of(puzzle)
    return {
        "puzzle": puzzle, "attempt": attempt, "solved": solved,
        "revealed_hints": revealed, "next_hint": next_hint, "hint_count": len(hints),
        "errors": errors, "max_points": scoring.puzzle_base_points(puzzle),
        "current_points": scoring.compute_points(puzzle, errors, revealed, rank),
        "competitive": competitive,
        "bonuses": scoring.bonuses(puzzle, rank, errors, revealed) if competitive else [],
        "podium": competition.podium(puzzle) if competitive else [],
        "podium_open": competition.next_rank(puzzle) <= len(scoring.PODIUM_BONUS) if competitive else False,
        "step": step, "steps": steps,
        "date": scoring.unlock_date(puzzle), "hour": scoring.RELEASE_HOUR[puzzle.kind],
        "other": _other_track(request, puzzle), **_neighbours(request, puzzle),
        # Le fragment d'histoire n'est envoyé au template qu'une fois le puzzle résolu.
        "story": puzzle.story if attempt and attempt.solved else "",
    }


def _neighbours(request, puzzle):
    """Puzzles voisins dans la même piste, pour enchaîner sans repasser par l'accueil.

    Le précédent est le plus proche déjà ouvert ; le suivant est le prochain publié, avec sa date s'il est encore
    verrouillé (son titre n'est alors pas affiché)."""
    track = list(Puzzle.objects.filter(kind=puzzle.kind).only("id", "kind", "day", "title", "unlock_date")
                 .order_by("day"))
    index = next(i for i, p in enumerate(track) if p.pk == puzzle.pk)
    solved = set(Attempt.objects.filter(user=request.user, puzzle__in=track, solved_at__isnull=False)
                 .values_list("puzzle_id", flat=True))

    def describe(other):
        other.unlocked = scoring.is_unlocked(other, request.user)
        other.done = other.pk in solved
        other.step = _step_of(other)[0]
        other.date = scoring.unlock_date(other)
        other.hour = scoring.RELEASE_HOUR[other.kind]
        return other

    previous = next((describe(p) for p in reversed(track[:index]) if scoring.is_unlocked(p, request.user)), None)
    following = describe(track[index + 1]) if index + 1 < len(track) else None
    return {"previous": previous, "following": following}


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
    # Premier affichage (suivi anti-triche) : une seule écriture, à la création de la progression.
    Attempt.objects.get_or_create(user=request.user, puzzle=puzzle, defaults={"first_seen_at": timezone.now()})
    return render(request, "avent2026/puzzle.html", _puzzle_context(request, puzzle))


def _back_to_answer(puzzle):
    """Retour au puzzle, calé sur le bloc réponse (messages, points, indices) : sur mobile, le résultat est sinon
    hors de l'écran, sous un long énoncé."""
    return redirect(reverse("avent2026:puzzle", args=[puzzle.id]) + "#resultat")


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
        else:
            given = request.POST.get("answer", "")
            correct = scoring.is_correct(puzzle, given)
            # Journal des réponses envoyées (suivi staff), conservé même si la progression est remise à zéro.
            Submission.objects.create(user=request.user, puzzle=puzzle, answer=given.strip()[:200], correct=correct,
                                      ip=client_ip(request))
            if correct:
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
    return _back_to_answer(puzzle)


@login_required
@require_POST
def reveal_hint(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    if not scoring.is_unlocked(puzzle, request.user):
        return _locked_response(request, puzzle.day, puzzle)
    if Attempt.objects.filter(user=request.user, puzzle=puzzle, solved_at__isnull=False).exists():
        return _back_to_answer(puzzle)
    # Indices révélés dans l'ordre : on donne toujours le prochain non révélé.
    hint = puzzle.hints.exclude(reveals__user=request.user).order_by("number").first()
    if hint:
        HintReveal.objects.get_or_create(user=request.user, hint=hint)
        lost = " et le bonus « sans indice »" if puzzle.kind in scoring.BONUS_KINDS else ""
        messages.info(request, f"Indice révélé (−{scoring.hint_cost(hint)} points{lost} si tu trouves).")
    return _back_to_answer(puzzle)


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
    # Le staff joue pour tester : il n'apparaît pas plus au classement qu'au podium.
    rows = (Attempt.objects.filter(solved_at__isnull=False, user__is_staff=False)
            .values("user__username", "puzzle__kind").annotate(total=Sum("points"), solved=Count("id")))
    board = {Puzzle.ENIGME: [], Puzzle.DEVINETTE: [], "total": defaultdict(lambda: [0, 0])}
    for r in rows:
        board[r["puzzle__kind"]].append({"name": r["user__username"], "points": r["total"], "solved": r["solved"]})
        board["total"][r["user__username"]][0] += r["total"]
        board["total"][r["user__username"]][1] += r["solved"]
    for kind in (Puzzle.ENIGME, Puzzle.DEVINETTE):
        board[kind].sort(key=lambda r: (-r["points"], r["name"]))
    total = sorted(({"name": n, "points": p, "solved": c} for n, (p, c) in board["total"].items()),
                   key=lambda r: (-r["points"], r["name"]))
    me = request.user.username
    my_rank = next((place for place, r in enumerate(total, start=1) if r["name"] == me), None)
    return render(request, "avent2026/leaderboard.html", {
        "enigmes": board[Puzzle.ENIGME], "devinettes": board[Puzzle.DEVINETTE], "total": total,
        "me": me, "my_rank": my_rank, "players": len(total),
        "verrous": competition.verrous(), "titles": competition.titles(),
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


SUIVI_VUES = [("temps", "Temps de réponse"), ("reponses", "Réponses"), ("connexions", "Connexions")]
SUIVI_PAR_PAGE = 50


def _int_param(request, name, default=None):
    try:
        return int(request.GET.get(name, ""))
    except ValueError:
        return default


@login_required
def tracking(request):
    """Suivi staff : temps de réponse (détection de triche), réponses envoyées, connexions."""
    if not request.user.is_staff:
        raise Http404
    vue = request.GET.get("vue")
    if vue not in dict(SUIVI_VUES):
        vue = SUIVI_VUES[0][0]
    include_staff = request.GET.get("staff") == "1"
    user_id = _int_param(request, "joueur")
    puzzle_id = _int_param(request, "puzzle")
    seuil = max(1, _int_param(request, "seuil", suivi.SEUIL_DEFAUT))
    order = "recent" if request.GET.get("tri") == "recent" else "rapide"

    ctx = {"vue": vue, "vues": SUIVI_VUES, "include_staff": include_staff, "user_id": user_id,
           "puzzle_id": puzzle_id, "seuil": seuil, "order": order}
    if vue == "temps":
        items = suivi.response_times(include_staff, seuil, user_id, puzzle_id, order)
    elif vue == "reponses":
        items = suivi.submissions(include_staff, user_id, puzzle_id)
    else:
        items = suivi.login_events(include_staff, user_id)
        ctx["summary"] = suivi.users_summary(include_staff)
        ctx["shared_ips"] = suivi.shared_ips(include_staff)
    page = Paginator(items, SUIVI_PAR_PAGE).get_page(request.GET.get("page"))
    if vue == "reponses":
        page.object_list = suivi.with_delay(list(page.object_list))
    query = request.GET.copy()
    query.pop("page", None)
    ctx.update({
        "page": page, "query": query.urlencode(),
        "players": get_user_model().objects.order_by("username").values_list("id", "username"),
        "puzzles": Puzzle.objects.only("id", "kind", "day", "title"),
    })
    return render(request, "avent2026/suivi.html", ctx)
