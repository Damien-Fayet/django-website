"""Règles de points et de déblocage, regroupées pour itérer facilement."""
import unicodedata
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

YEAR = 2026
TZ = ZoneInfo("Europe/Paris")

# Points de base par type (surchargeables par puzzle via base_points).
BASE_POINTS = {
    "enigme": 100,
    "devinette": 50,
}
DEFAULT_HINT_COST = 15
ERROR_PENALTY = 5
MIN_POINTS = 10  # une bonne réponse rapporte toujours au moins ça

# Heure (de Paris) à laquelle le puzzle du jour se débloque. Les énigmes sortent à 6 h pour que les couche-tard
# et les lève-tôt partent à égalité ; les devinettes, sans course, sortent à minuit.
RELEASE_HOUR = {"enigme": 6, "devinette": 0}

# Bonus de la piste compétitive (énigmes seulement), ajoutés aux points une fois la pénalité retirée. Il n'y a
# volontairement pas de bonus de rapidité au-delà du podium : il favoriserait ceux qui ont le plus de temps.
BONUS_KINDS = ("enigme",)
PODIUM_BONUS = (50, 30, 20)  # 1er, 2e et 3e à résoudre ce verrou (le staff n'est pas compté)
PODIUM_LABELS = ("Premier à briser ce verrou", "Deuxième à briser ce verrou", "Troisième à briser ce verrou")
NO_HINT_BONUS = 25
NO_ERROR_BONUS = 10


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
    return BASE_POINTS[puzzle.kind]


def hint_cost(hint):
    return hint.cost if hint.cost is not None else DEFAULT_HINT_COST


def bonuses(puzzle, rank, errors, hints):
    """Bonus obtenus, sous la forme [(libellé, points)] : podium (`rank` = place parmi les joueurs, None si hors
    classement), sans indice, sans faute. Vide pour les pistes sans compétition."""
    if puzzle.kind not in BONUS_KINDS:
        return []
    result = []
    if rank is not None and 1 <= rank <= len(PODIUM_BONUS):
        result.append((PODIUM_LABELS[rank - 1], PODIUM_BONUS[rank - 1]))
    if not hints:
        result.append(("Sans indice", NO_HINT_BONUS))
    if errors == 0:
        result.append(("Sans faute", NO_ERROR_BONUS))
    return result


def compute_points(puzzle, errors, hints, rank=None):
    penalty = errors * ERROR_PENALTY + sum(hint_cost(h) for h in hints)
    bonus = sum(points for _label, points in bonuses(puzzle, rank, errors, hints))
    return max(MIN_POINTS, puzzle_base_points(puzzle) - penalty) + bonus


def unlock_date(puzzle):
    return puzzle.unlock_date or date(YEAR, 12, puzzle.day)


def release_at(kind, day, on=None):
    """Instant du déblocage du jour `day` pour la piste `kind` (`on` : date imposée, sinon le `day` décembre)."""
    return datetime.combine(on or date(YEAR, 12, day), time(RELEASE_HOUR[kind]), tzinfo=TZ)


def unlock_at(puzzle):
    return release_at(puzzle.kind, puzzle.day, puzzle.unlock_date)


def now():
    return timezone.now().astimezone(TZ)


def _sees_everything(user):
    """Les admins (staff ou superutilisateurs) et AVENT2026_UNLOCK_ALL voient tout, sans limite de date."""
    return getattr(settings, "AVENT2026_UNLOCK_ALL", False) or (
        user is not None and (user.is_staff or user.is_superuser))


def is_unlocked(puzzle, user=None):
    """Débloqué quand l'heure de sortie de sa piste est passée."""
    return _sees_everything(user) or now() >= unlock_at(puzzle)


def is_day_unlocked(kind, day, user=None):
    """Même chose pour un jour où aucun puzzle n'est encore publié."""
    return _sees_everything(user) or now() >= release_at(kind, day)
