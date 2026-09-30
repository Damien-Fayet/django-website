"""Règles de points et de déblocage, regroupées pour itérer facilement."""
import unicodedata
from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

YEAR = 2026
TZ = ZoneInfo("Europe/Paris")

# Points de base par type et difficulté (surchargeables par puzzle via base_points).
BASE_POINTS = {
    ("enigme", "facile"): 100,
    ("enigme", "difficile"): 200,
    ("devinette", "facile"): 50,
    ("devinette", "difficile"): 100,
}
DEFAULT_HINT_COST = 15
ERROR_PENALTY = 5
MIN_POINTS = 10  # une bonne réponse rapporte toujours au moins ça


def normalize(value):
    """Minuscules, sans accents ni ponctuation, espaces réduits."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    value = "".join(c if c.isalnum() else " " for c in value)
    return " ".join(value.split())


def is_correct(puzzle, given):
    given = normalize(given)
    return bool(given) and given in {normalize(a) for a in puzzle.answers.splitlines() if a.strip()}


def puzzle_base_points(puzzle):
    if puzzle.base_points is not None:
        return puzzle.base_points
    return BASE_POINTS[(puzzle.kind, puzzle.difficulty)]


def hint_cost(hint):
    return hint.cost if hint.cost is not None else DEFAULT_HINT_COST


def compute_points(puzzle, errors, hints):
    penalty = errors * ERROR_PENALTY + sum(hint_cost(h) for h in hints)
    return max(MIN_POINTS, puzzle_base_points(puzzle) - penalty)


def unlock_date(puzzle):
    return puzzle.unlock_date or date(YEAR, 12, puzzle.day)


def today():
    return timezone.now().astimezone(TZ).date()


def is_unlocked(puzzle_or_day, user=None):
    """Débloqué si la date est passée. Les admins (staff) et AVENT2026_UNLOCK_ALL voient tout."""
    if getattr(settings, "AVENT2026_UNLOCK_ALL", False) or (user is not None and user.is_staff):
        return True
    if isinstance(puzzle_or_day, int):
        return today() >= date(YEAR, 12, puzzle_or_day)
    return today() >= unlock_date(puzzle_or_day)
