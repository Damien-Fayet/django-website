"""Hauts-faits : de petits défis pour rire, décernés d'après ce que chacun a fait (réponses, indices, résolutions).

Rien n'est stocké : tout est recalculé à la demande depuis `Attempt`, `HintReveal`, `Submission` et `LeaderboardDay`
(le compteur de visites du classement ; quelques dizaines de joueurs, quelques milliers de lignes : quatre requêtes
suffisent). Ajouter un haut-fait = ajouter une fonction de
test et une entrée dans `HAUTS_FAITS` ; l'icône est un symbole du sprite `templates/avent2026/_sprite.html`.

Le staff joue pour tester : il peut décrocher des hauts-faits (utile pour les voir), mais n'apparaît pas dans les
listes publiques (`by_user`).
"""
from collections import Counter, defaultdict
from typing import Callable, NamedTuple

from . import scoring, village
from .models import Attempt, HintReveal, LeaderboardDay, Submission

# Seuils, ici pour être faciles à retoucher (et à tester).
TRY_HARDER_TRIES = 5            # « plus de 5 essais » : au moins 6 réponses envoyées sur une même énigme ou devinette
DISQUE_RAYE_ERRORS = 10         # mauvaises réponses envoyées au total (toutes énigmes et devinettes confondues)
# Paliers « du premier coup » et « sans indice » : nombre d'énigmes ou de devinettes de la piste, un haut-fait par palier.
FIRST_TRY_TIERS = {"enigme": (1, 5, 8), "devinette": (1, 5, 10, 20)}
NO_HINT_TIERS = {"enigme": (1, 3, 5, 8), "devinette": (1, 5, 10, 20)}
HINT_LOVER_TIERS = (5, 10)      # énigmes ou devinettes où l'on a pris au moins un indice
BOARD_DAILY_VIEWS = 3           # « plus de 3 fois par jour » : au moins 4 visites du classement le même jour
BOARD_TOTAL_VIEWS = 100         # « plus de 100 fois au total » : au moins 101 visites
EARLY_BIRD_HOURS = (6, 8)       # une énigme résolue entre 6 h et 8 h (heure de Paris)
NIGHT_OWL_BEFORE = 5            # une énigme ou devinette résolue avant 5 h du matin
STREAK_DAYS = 7                 # jours de suite avec au moins une énigme ou devinette résolue


class Dossier:
    """Ce qu'on sait d'un joueur pour juger ses hauts-faits."""

    def __init__(self):
        self.solved = []                     # [{puzzle_id, kind, day, errors, rank, at}] (at : heure de Paris)
        self.hinted = set()                  # puzzles où un indice a été révélé
        self.tries = Counter()               # puzzle_id -> nombre de réponses envoyées
        self.wrong_total = 0                 # mauvaises réponses envoyées, toutes énigmes et devinettes confondues
        self.board_views = {}                # jour (heure de Paris) -> visites du classement ce jour-là


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
            d.wrong_total += 1
    for user_id, day, views in narrow(LeaderboardDay.objects.all()).values_list("user_id", "day", "views"):
        dossiers[user_id].board_views[day] = views
    return dossiers


# ---- Les tests : chacun reçoit un `Dossier` et répond par oui ou non ------------------------------------------------

def _try_harder(d):
    return any(n > TRY_HARDER_TRIES for n in d.tries.values())


def _disque_raye(d):
    return d.wrong_total >= DISQUE_RAYE_ERRORS


def _brise_chaine(d):
    return any(s["kind"] == "enigme" and s["rank"] == 1 for s in d.solved)


def _podium(d):
    return any(s["kind"] == "enigme" and s["rank"] is not None and 1 <= s["rank"] <= len(scoring.PODIUM_BONUS)
               for s in d.solved)


def _premier_coup(kind, count):
    """Au moins `count` énigmes (ou devinettes) résolues dès la première réponse (aucune erreur avant la bonne)."""
    return lambda d: sum(1 for s in d.solved if s["kind"] == kind and s["errors"] == 0) >= count


def _sans_indice(kind, count):
    """Au moins `count` énigmes (ou devinettes) résolues sans le moindre indice."""
    return lambda d: sum(1 for s in d.solved if s["kind"] == kind and s["puzzle_id"] not in d.hinted) >= count


def _accro(count):
    return lambda d: len(d.hinted) >= count


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


def _serrurier(d):
    return sum(1 for s in d.solved if s["kind"] == "enigme") >= len(village.ENIGME_DAYS)


def _fana_du_jour(d):
    return any(n > BOARD_DAILY_VIEWS for n in d.board_views.values())


def _abonne(d):
    return sum(d.board_views.values()) > BOARD_TOTAL_VIEWS


def _allumeur(d):
    return sum(1 for s in d.solved if s["kind"] == "devinette") >= len(village.CARTES["devinette"].days)


class HautFait(NamedTuple):
    key: str
    name: str
    description: str
    icon: str            # symbole du sprite (sans le préfixe « ic- »)
    test: Callable
    family: str = ""     # les paliers d'une même série partagent une famille ; les pastilles ne montrent que le plus haut


def _resolues(count, kind):
    """« Une énigme résolue », « 5 devinettes résolues »."""
    noun = "énigme" if kind == "enigme" else "devinette"
    return f"Une {noun} résolue" if count == 1 else f"{count} {noun}s résolues"


def _nombre(count, kind):
    noun = "énigme" if kind == "enigme" else "devinette"
    return f"{count} {noun}{'s' if count > 1 else ''}"


def _premier_coup_faits():
    """« Du premier coup » : un haut-fait par palier et par piste (aucune erreur avant la bonne réponse)."""
    for kind, tiers in FIRST_TRY_TIERS.items():
        for count in tiers:
            yield HautFait(f"premier_coup_{kind}_{count}", f"Du premier coup : {_nombre(count, kind)}",
                           f"{_resolues(count, kind)} dès la première réponse.", "cible", _premier_coup(kind, count),
                           family=f"premier_coup_{kind}")


def _sans_indice_faits():
    """« Sans indice » : un haut-fait par palier et par piste."""
    for kind, tiers in NO_HINT_TIERS.items():
        for count in tiers:
            yield HautFait(f"sans_indice_{kind}_{count}", f"Sans indice : {_nombre(count, kind)}",
                           f"{_resolues(count, kind)} sans le moindre indice.", "coche", _sans_indice(kind, count),
                           family=f"sans_indice_{kind}")


def _accro_faits():
    for count in HINT_LOVER_TIERS:
        yield HautFait(f"accro_{count}", f"Accro aux indices : {count} énigmes ou devinettes",
                       f"Des indices pris sur {count} énigmes ou devinettes différentes. Il n'y a pas de honte.",
                       "ampoule", _accro(count), family="accro")


HAUTS_FAITS = [
    HautFait("try_harder", "Try-Harder", "Plus de 5 essais sur une même énigme ou devinette. L'obstination paie.",
             "flamme", _try_harder),
    HautFait("disque_raye", "Disque rayé", f"{DISQUE_RAYE_ERRORS} mauvaises réponses envoyées au total. Ça ira mieux la prochaine.",
             "disque", _disque_raye),
    HautFait("brise_chaine", "Brise-chaîne", "Premier de tous à briser un verrou de la cellule.", "eclair", _brise_chaine),
    HautFait("podium", "Médaillé", "Sur le podium d'un verrou : parmi les trois premiers à le briser.", "medaille", _podium),
    *_premier_coup_faits(),
    *_sans_indice_faits(),
    *_accro_faits(),
    HautFait("leve_tot", "Lève-tôt", "Une énigme résolue entre 6 h et 8 h du matin, heure de Paris.", "soleil", _leve_tot),
    HautFait("noctambule", "Noctambule", "Une énigme ou une devinette résolue entre minuit et 5 h du matin, heure de Paris.", "lune", _noctambule),
    HautFait("double", "Doublé du jour",
             "L'énigme et la devinette d'un même jour toutes les deux résolues.", "double", _double),
    HautFait("assidu", "Assidu", f"Au moins une énigme ou une devinette résolue {STREAK_DAYS} jours de suite.", "calendrier", _assidu),
    HautFait("serrurier", "Serrurier", "Les 8 énigmes résolues : tous les verrous de la cellule sont brisés.", "cadenas", _serrurier),
    HautFait("allumeur", "Grand allumeur", "Les 24 devinettes résolues : tout le village est éclairé.", "lanterne", _allumeur),
    HautFait("fana_du_jour", "Fana du classement",
             f"Le classement consulté plus de {BOARD_DAILY_VIEWS} fois dans la même journée. On ne se refait pas.",
             "classement", _fana_du_jour, family="classement"),
    HautFait("abonne", "Abonné au classement",
             f"Le classement consulté plus de {BOARD_TOTAL_VIEWS} fois au total. Il doit avoir des raisons.",
             "classement", _abonne, family="classement"),
]
BY_KEY = {h.key: h for h in HAUTS_FAITS}


def badges(keys):
    """Les hauts-faits de `keys` à montrer en pastilles : pour une série à paliers, seulement le plus haut atteint
    (la liste `HAUTS_FAITS` range les paliers du plus petit au plus grand)."""
    best = {}
    for h in HAUTS_FAITS:
        if h.key in keys:
            best[h.family or h.key] = h  # le dernier palier de la famille écrase les précédents
    return sorted(best.values(), key=HAUTS_FAITS.index)


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
