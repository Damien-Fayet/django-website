"""Les deux villages qui se rallument : paliers, histoire, illustrations et position des lumières.

Un village par piste : le village des énigmes et le village des devinettes, chacun avec 24 lumières (une par jour).
La progression se mesure en lumières allumées, c'est-à-dire en puzzles résolus (24 jours × 2 villages = 48).
Les points ne servent qu'au classement.

Illustrations : une image par village dans `static/avent2026/img/` (voir ILLUSTRATIONS_VILLAGES.md). Tant qu'une
image manque, la scène reste jouable sur un fond de nuit neigeuse dessiné en CSS.
Positions des lumières : `lights.json` (en % de l'image), à régler avec la page de calibrage (réservée au staff).
"""
import json
from functools import lru_cache
from pathlib import Path

from django.contrib.staticfiles import finders

TOTAL = 48
DAYS = 24

# Une entrée par village, dans l'ordre d'affichage : (clé = type de puzzle, nom, fichiers acceptés, description pour l'image)
VILLAGES = [
    ("enigme", "Le village des énigmes", "village-enigmes",
     "Un village enneigé la nuit : les fenêtres des maisons attendent d'être rallumées."),
    ("devinette", "Le village des devinettes", "village-devinettes",
     "Un village enneigé la nuit : les lanternes attendent d'être rallumées."),
]
KINDS = tuple(kind for kind, *_ in VILLAGES)
IMAGE_EXTENSIONS = ("webp", "jpg", "jpeg", "png")

# Villages dessinés étape par étape : une image par nombre de puzzles résolus (0 à 24), au lieu de 24 lumières
# posées sur une seule image. Clé = type de puzzle ; valeur = (dossier sous static/avent2026/img/, nom du fichier).
CARTES = {"devinette": ("carte-devinettes", "village-iso-etape-{step:02d}")}

# (nombre de lumières allumées, titre du palier, description)
LEVELS = [
    (0,  "Villages éteints",       "La tempête a tout éteint. Seuls quelques flocons accrochent encore un peu de clarté."),
    (6,  "Premières lueurs",       "Quelques fenêtres vacillent. Les villages ne sont plus tout à fait seuls."),
    (14, "Les rues s'éveillent",   "Les lumières courent déjà d'une maison à l'autre."),
    (24, "Les villages respirent", "La moitié des lumières brille. La neige tombe plus doucement."),
    (34, "Presque en fête",        "D'une colline à l'autre, les villages se répondent."),
    (44, "Les places s'illuminent", "Il ne manque plus que les dernières lumières, celles des grands sapins."),
]

PROLOGUE = (
    "Une tempête de neige a coupé le courant la veille du 1er décembre. Deux villages voisins, celui des énigmes "
    "et celui des devinettes, sont plongés dans le noir, et le grand sapin de chaque place n'a même plus son étoile. "
    "Vous êtes les allumeurs. Chaque énigme résolue rallume une lumière dans le premier village, chaque devinette "
    "une lumière dans le second. Si les deux brillent avant le soir du 24, Noël aura bien lieu."
)

EPILOGUE = (
    "La dernière lumière s'allume. Sur les deux places, les grands sapins se mettent à scintiller et, "
    "d'une colline à l'autre, les villages se répondent. Les tables sont dressées, les fenêtres brillent, "
    "les cheminées fument : le réveillon peut commencer."
)

LIGHTS_FILE = Path(__file__).with_name("lights.json")


def _default_positions():
    """Positions provisoires : 4 rangées de 6 lumières, de gauche à droite puis de haut en bas."""
    return [[round(12 + col * 15.2, 1), round(30 + row * 17, 1)] for row in range(4) for col in range(6)]


@lru_cache(maxsize=1)
def _all_positions():
    try:
        data = json.loads(LIGHTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    positions = {}
    for kind in KINDS:
        points = data.get(kind)
        valid = (isinstance(points, list) and len(points) == DAYS
                 and all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p)
                         and 0 <= p[0] <= 100 and 0 <= p[1] <= 100 for p in points))
        positions[kind] = [tuple(p) for p in points] if valid else [tuple(p) for p in _default_positions()]
    return positions


def light_position(kind, day):
    """Position (x, y) en % de la lumière du jour `day` (1 à 24) dans le village du type `kind`."""
    return _all_positions()[kind][day - 1]


def image_path(kind):
    """Chemin statique de l'illustration du village, ou None si elle n'a pas encore été déposée."""
    base = {k: stem for k, _n, stem, _d in VILLAGES}[kind]
    for ext in IMAGE_EXTENSIONS:
        path = f"avent2026/img/{base}.{ext}"
        if finders.find(path):
            return path
    return None


def carte_image_path(kind, step):
    """Chemin statique de l'image « étape `step` » (0 à 24 bâtiments allumés), ou None si le fichier manque."""
    folder, pattern = CARTES[kind]
    base = f"avent2026/img/{folder}/{pattern.format(step=max(0, min(DAYS, step)))}"
    for ext in IMAGE_EXTENSIONS:
        if finders.find(f"{base}.{ext}"):
            return f"{base}.{ext}"
    return None


def village_info(kind):
    return next({"kind": k, "name": name, "stem": stem, "alt": alt} for k, name, stem, alt in VILLAGES if k == kind)


def village_state(lit):
    """État des villages pour un nombre donné de lumières allumées (sur 48)."""
    lit = max(0, min(TOTAL, lit or 0))
    level = 0
    for index, (threshold, *_rest) in enumerate(LEVELS):
        if lit >= threshold:
            level = index
    next_level = LEVELS[level + 1] if level + 1 < len(LEVELS) else None
    if next_level is None:
        progress = 100
    else:
        start = LEVELS[level][0]
        progress = int((lit - start) * 100 / (next_level[0] - start))
    return {
        "lit": lit,
        "total": TOTAL,
        "level": level + 1,
        "max_level": len(LEVELS),
        "title": LEVELS[level][1],
        "description": LEVELS[level][2],
        "next_threshold": next_level[0] if next_level else None,
        "next_title": next_level[1] if next_level else None,
        "progress_pct": progress,
        "calm": round(lit / TOTAL, 2),  # 0 : pleine tempête, 1 : tout est allumé
    }
