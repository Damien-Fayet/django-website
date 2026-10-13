"""La course aux verrous : podium de chaque énigme et titres (Libérateur, Sans filet).

Le staff joue pour tester : il n'est jamais compté dans la course (ni podium, ni titres).
"""
from django.db.models import Count, Max, Q

from . import scoring, village
from .models import Attempt, HintReveal, Puzzle


def _solvers(puzzle):
    return Attempt.objects.filter(puzzle=puzzle, solved_at__isnull=False, user__is_staff=False)


def rank_of(attempt):
    """Place d'une résolution déjà enregistrée : 1 + les résolutions plus anciennes (à égalité, la plus ancienne en
    base passe devant). None pour le staff."""
    if attempt.user.is_staff:
        return None
    earlier = _solvers(attempt.puzzle).filter(
        Q(solved_at__lt=attempt.solved_at) | Q(solved_at=attempt.solved_at, pk__lt=attempt.pk))
    return earlier.count() + 1


def next_rank(puzzle):
    """Place qu'aurait quelqu'un qui résoudrait maintenant."""
    return _solvers(puzzle).count() + 1


def podium(puzzle):
    """Les premiers à avoir résolu le puzzle : [(place, nom, instant)]."""
    rows = (_solvers(puzzle).select_related("user").order_by("solved_at", "pk")[:len(scoring.PODIUM_BONUS)])
    return [(place, a.user.username, a.solved_at.astimezone(scoring.TZ))
            for place, a in enumerate(rows, start=1)]


def verrous():
    """Un podium par énigme déjà sortie, dans l'ordre de la cellule : [{puzzle, step, podium}]."""
    puzzles = {p.day: p for p in Puzzle.objects.filter(kind=Puzzle.ENIGME, day__in=village.ENIGME_DAYS)}
    result = []
    for step, day in enumerate(village.ENIGME_DAYS, start=1):
        puzzle = puzzles.get(day)
        if puzzle is not None and scoring.is_unlocked(puzzle):
            result.append({"puzzle": puzzle, "step": step, "podium": podium(puzzle)})
    return result


def titles():
    """Les titres de la cellule : le Libérateur (premier à avoir brisé les 8 verrous) et les « Sans filet »
    (les 8 verrous brisés sans un seul indice). Vides tant que personne n'a tout fini."""
    total = len(village.ENIGME_DAYS)
    finishers = (Attempt.objects
                 .filter(puzzle__kind=Puzzle.ENIGME, puzzle__day__in=village.ENIGME_DAYS,
                         solved_at__isnull=False, user__is_staff=False)
                 .values("user_id", "user__username")
                 .annotate(n=Count("id"), done_at=Max("solved_at"))
                 .filter(n=total).order_by("done_at", "user_id"))
    finishers = list(finishers)
    used_hints = set(HintReveal.objects.filter(hint__puzzle__kind=Puzzle.ENIGME).values_list("user_id", flat=True))
    return {
        "liberateur": finishers[0] if finishers else None,
        "sans_filet": sorted(f["user__username"] for f in finishers if f["user_id"] not in used_hints),
    }
