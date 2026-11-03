"""Hauts-faits : de petits défis pour rire, décernés d'après ce que chacun a fait (réponses, indices, résolutions).

Rien n'est stocké : tout est recalculé à la demande depuis `Attempt`, `HintReveal` et `Submission` (quelques dizaines
de joueurs, quelques milliers de lignes : trois requêtes suffisent). Ajouter un haut-fait = ajouter une fonction de
test et une entrée dans `HAUTS_FAITS` ; l'icône est un symbole du sprite `templates/avent2026/_sprite.html`.

Le staff joue pour tester : il peut décrocher des hauts-faits (utile pour les voir), mais n'apparaît pas dans les
listes publiques (`by_user`).
"""
from collections import Counter, defaultdict
from typing import Callable, NamedTuple

from . import scoring, village
from .models import Attempt, HintReveal, Submission

# Seuils, ici pour être faciles à retoucher (et à tester).
TRY_HARDER_TRIES = 5            # « plus de 5 essais » : au moins 6 réponses envoyées sur un même puzzle
DISQUE_RAYE_REPEATS = 3         # la même mauvaise réponse envoyée 3 fois sur un même puzzle
FIRST_TRY_COUNT = 10            # puzzles résolus du premier coup
NO_HINT_COUNT = 10              # puzzles résolus sans aucun indice
HINT_LOVER_COUNT = 5            # puzzles où l'on a pris au moins un indice
EARLY_BIRD_HOURS = (6, 8)       # une énigme résolue entre 6 h et 8 h (heure de Paris)
NIGHT_OWL_BEFORE = 5            # un puzzle résolu avant 5 h du matin
STREAK_DAYS = 7                 # jours de suite avec au moins un puzzle résolu


class Dossier:
    """Ce qu'on sait d'un joueur pour juger ses hauts-faits."""

    def __init__(self):
        self.solved = []                     # [{puzzle_id, kind, day, errors, rank, at}] (at : heure de Paris)
        self.hinted = set()                  # puzzles où un indice a été révélé
        self.tries = Counter()               # puzzle_id -> nombre de réponses envoyées
        self.wrong = defaultdict(Counter)    # puzzle_id -> {mauvaise réponse normalisée: fois envoyée}


def _dossiers(user_ids=None, include_staff=True):
    """Un `Dossier` par joueur (`user_ids` : seulement ceux-là ; `include_staff=False` : hors staff)."""
    def narrow(queryset):
        if user_ids is not None:
            queryset = queryset.filter(user_id__in=user_ids)
        return queryset if include_staff else queryset.filter(user__is_staff=False)

    dossiers = defaultdict(Dossier)
    for a in narrow(Attempt.objects.filter(solved_at__isnull=False)).values(
            "user_id", "puzzle_id", "puzzle__kind", "puzzle__day", "errors", "rank", "solved_at"):
        dossiers[a["user_id"]].solved.append({
            "puzzle_id": a["puzzle_id"], "kind": a["puzzle__kind"], "day": a["puzzle__day"], "errors": a["errors"],
            "rank": a["rank"], "at": a["solved_at"].astimezone(scoring.TZ)})
    for user_id, puzzle_id in narrow(HintReveal.objects.all()).values_list("user_id", "hint__puzzle_id"):
        dossiers[user_id].hinted.add(puzzle_id)
    for user_id, puzzle_id, answer, correct in narrow(Submission.objects.all()).values_list(
            "user_id", "puzzle_id", "answer", "correct"):
        d = dossiers[user_id]
        d.tries[puzzle_id] += 1
        if not correct and scoring.normalize(answer):
            d.wrong[puzzle_id][scoring.normalize(answer)] += 1
    return dossiers


# ---- Les tests : chacun reçoit un `Dossier` et répond par oui ou non ------------------------------------------------

def _try_harder(d):
    return any(n > TRY_HARDER_TRIES for n in d.tries.values())


def _disque_raye(d):
    return any(n >= DISQUE_RAYE_REPEATS for wrong in d.wrong.values() for n in wrong.values())


def _brise_chaine(d):
    return any(s["kind"] == "enigme" and s["rank"] == 1 for s in d.solved)


def _podium(d):
    return any(s["kind"] == "enigme" and s["rank"] is not None and 1 <= s["rank"] <= len(scoring.PODIUM_BONUS)
               for s in d.solved)


def _premier_coup(d):
    return sum(1 for s in d.solved if s["errors"] == 0) >= FIRST_TRY_COUNT


def _cerveau_seul(d):
    return sum(1 for s in d.solved if s["puzzle_id"] not in d.hinted) >= NO_HINT_COUNT


def _accro(d):
    return len(d.hinted) >= HINT_LOVER_COUNT


def _leve_tot(d):
    start, end = EARLY_BIRD_HOURS
    return any(s["kind"] == "enigme" and start <= s["at"].hour < end for s in d.solved)


def _noctambule(d):
    return any(s["at"].hour < NIGHT_OWL_BEFORE for s in d.solved)


def _double(d):
    days = {kind: {s["day"] for s in d.solved if s["kind"] == kind} for kind in ("enigme", "devinette")}
    return bool(days["enigme"] & days["devinette"])


def _assidu(d):
    days = sorted({s["at"].date().toordinal() for s in d.solved})
    run = best = 0
    for index, day in enumerate(days):
        run = run + 1 if index and day == days[index - 1] + 1 else 1
        best = max(best, run)
    return best >= STREAK_DAYS


def _allumeur(d):
    return sum(1 for s in d.solved if s["kind"] == "devinette") >= len(village.CARTES["devinette"].days)


class HautFait(NamedTuple):
    key: str
    name: str
    description: str
    icon: str            # symbole du sprite (sans le préfixe « ic- »)
    test: Callable


HAUTS_FAITS = [
    HautFait("try_harder", "Try-Harder", "Plus de 5 essais sur une même énigme ou devinette. L'obstination paie.",
             "flamme", _try_harder),
    HautFait("disque_raye", "Disque rayé", "La même mauvaise réponse envoyée 3 fois sur un même puzzle. Ça ira mieux la quatrième.",
             "disque", _disque_raye),
    HautFait("brise_chaine", "Brise-chaîne", "Premier de tous à briser un verrou de la cellule.", "eclair", _brise_chaine),
    HautFait("podium", "Médaillé", "Sur le podium d'un verrou : parmi les trois premiers à le briser.", "medaille", _podium),
    HautFait("premier_coup", "Du premier coup",
             f"{FIRST_TRY_COUNT} puzzles résolus dès la première réponse.", "cible", _premier_coup),
    HautFait("cerveau_seul", "Cerveau seul",
             f"{NO_HINT_COUNT} puzzles résolus sans le moindre indice.", "coche", _cerveau_seul),
    HautFait("accro", "Accro aux indices",
             f"Des indices pris sur {HINT_LOVER_COUNT} puzzles. Il n'y a pas de honte.", "ampoule", _accro),
    HautFait("leve_tot", "Lève-tôt", "Une énigme résolue entre 6 h et 8 h du matin, heure de Paris.", "soleil", _leve_tot),
    HautFait("noctambule", "Noctambule", "Un puzzle résolu avant 5 h du matin, heure de Paris.", "lune", _noctambule),
    HautFait("double", "Doublé du jour",
             "L'énigme et la devinette d'un même jour toutes les deux résolues.", "double", _double),
    HautFait("assidu", "Assidu", f"Au moins un puzzle résolu {STREAK_DAYS} jours de suite.", "calendrier", _assidu),
    HautFait("allumeur", "Grand allumeur", "Les 24 devinettes résolues : tout le village est éclairé.", "lanterne", _allumeur),
]
BY_KEY = {h.key: h for h in HAUTS_FAITS}


def _earned(dossier):
    return {h.key for h in HAUTS_FAITS if h.test(dossier)}


def keys_for(user):
    """Clés des hauts-faits décrochés par ce joueur (staff compris : il peut ainsi tout tester)."""
    dossiers = _dossiers([user.pk])
    return _earned(dossiers[user.pk]) if user.pk in dossiers else set()


def by_user():
    """{identifiant du joueur: clés de ses hauts-faits}, hors staff, pour les joueurs qui en ont au moins un."""
    result = {uid: _earned(d) for uid, d in _dossiers(include_staff=False).items()}
    return {uid: keys for uid, keys in result.items() if keys}


def new_for(user, before):
    """Hauts-faits décrochés depuis `before` (un ensemble de clés lu plus tôt), dans l'ordre de la liste."""
    now = keys_for(user)
    return [h for h in HAUTS_FAITS if h.key in now and h.key not in before]
