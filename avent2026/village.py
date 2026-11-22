"""Les deux pistes du jeu, dessinées étape par étape : le village (devinettes) et la cellule du Père Noël (énigmes).

Chaque piste a une carte : une image par nombre de puzzles résolus par le joueur (étape 0 jusqu'au nombre de jours
de la piste), voir `CARTES`. Le village des devinettes se rallume bâtiment par bâtiment (24 jours), le Père Noël est
libéré verrou par verrou (8 énigmes, les mardi 1er, mercredis et samedis de décembre).
La progression se mesure en étapes franchies, c'est-à-dire en puzzles résolus (24 + 8 = 32). Les points ne servent
qu'au classement.

Illustrations : voir ILLUSTRATIONS_VILLAGES.md (village) et ILLUSTRATIONS_ENIGMES.md (cellule). Tant qu'une image
manque, la carte reste jouable sur un fond sombre dessiné en CSS.
"""
from typing import NamedTuple

from django.contrib.staticfiles import finders

DAYS = 24
# Jours du calendrier (décembre 2026) où une énigme est publiée : mardi 1er (échauffement), puis chaque mercredi
# et chaque samedi jusqu'au 23. Le jour d'une énigme reste son jour du mois (`Puzzle.day`).
ENIGME_DAYS = (1, 2, 5, 9, 12, 16, 19, 23)
IMAGE_EXTENSIONS = ("webp", "jpg", "jpeg", "png")


class Carte(NamedTuple):
    name: str     # titre de la piste
    alt: str      # description de l'image pour les lecteurs d'écran
    noun: str     # « bâtiment », « verrou »
    done: str     # « allumé », « brisé » (accordé avec le nom)
    step: str     # « Jour », « Verrou » : étiquette d'une étape dans la liste
    days: tuple   # jours du calendrier où la piste publie un puzzle, dans l'ordre
    folder: str   # dossier sous static/avent2026/img/
    pattern: str  # nom de fichier, sans extension, avec {step}
    dated: bool   # afficher la date (jour de la semaine et du mois) sur chaque étape


# Dans l'ordre d'affichage. Clé = type de puzzle.
CARTES = {
    "enigme": Carte(
        name="La cellule du Père Noël", noun="verrou", done="brisé", step="Verrou", days=ENIGME_DAYS, dated=True,
        alt="La cellule où le Père Noël est enchaîné", folder="carte-enigmes", pattern="cellule-etape-{step:02d}"),
    "devinette": Carte(
        name="Le village des devinettes", noun="bâtiment", done="allumé", step="Jour", days=tuple(range(1, DAYS + 1)),
        dated=False, alt="Le village enneigé qui se rallume", folder="carte-devinettes",
        pattern="village-iso-etape-{step:02d}"),
}
KINDS = tuple(CARTES)
TOTAL = sum(len(carte.days) for carte in CARTES.values())  # 32 : étapes à franchir pour tout finir
# Dernier jour de chaque piste : l'épilogue s'affiche quand les puzzles publiés de ces jours sont tous résolus.
FINAL_DAYS = {kind: carte.days[-1] for kind, carte in CARTES.items()}

# Prologue : un dossier (titre, récit, message anonyme glissé sous la porte, mot de la fin). Le coupable reste inconnu :
# les fragments d'histoire (`Puzzle.story`) saisis dans l'admin ne doivent pas être contredits.
PROLOGUE = {
    "titre": "La nuit où le village s'est éteint",
    "recit": (
        "Il était 23 h 58, la veille du 1er décembre. Les dernières fenêtres du village brillaient encore quand le "
        "vent s'est levé d'un coup, sans un nuage. La neige est tombée en rideau et, à minuit pile, tout s'est "
        "éteint : les lampadaires, les guirlandes, et même l'étoile du grand sapin.",
        "On a parlé d'une tempête. Pourtant, pas une branche cassée, pas une tuile envolée, et un silence trop "
        "parfait pour une nuit de bourrasques. Au matin, la maison du Père Noël était vide. Des traces de pas dans "
        "la neige, qui s'arrêtent net au milieu de la place, comme si quelqu'un avait effacé la suite.",
        "C'est alors qu'un message sans signature a été glissé sous la porte de chacun d'entre vous :",
    ),
    "message": (
        "Cette tempête n'était qu'un écran de fumée. Il est retenu dans une cellule, enchaîné par huit verrous. "
        "Rallumez le village, une lumière à la fois, pour qu'il sache que vous êtes là. Brisez les verrous un à un, "
        "avant le soir du 24. Après, il sera trop tard."
    ),
    "signature": "Un ami. Peut-être.",
    "fin": (
        "Chacun avance à son rythme, mais le nom des premiers à briser chaque verrou sera connu de tous. "
        "Et peut-être de quelqu'un d'autre."
    ),
}

EPILOGUE = (
    "La dernière lumière s'allume sur la place, l'étoile du grand sapin se remet à briller et, dans un dernier "
    "fracas de chaînes, la porte de la cellule s'ouvre. Le Père Noël est libre. Les tables sont dressées, les "
    "fenêtres brillent, les cheminées fument : le réveillon peut commencer."
)


def carte_image_path(kind, step):
    """Chemin statique de l'image « étape `step` » de la carte, ou None si le fichier manque."""
    carte = CARTES[kind]
    base = f"avent2026/img/{carte.folder}/{carte.pattern.format(step=max(0, min(len(carte.days), step)))}"
    for ext in IMAGE_EXTENSIONS:
        if finders.find(f"{base}.{ext}"):
            return f"{base}.{ext}"
    return None


def counter(kind, count):
    """« 0 verrou brisé », « 1 bâtiment allumé », « 3 bâtiments allumés » (singulier pour 0 et 1)."""
    carte = CARTES[kind]
    s = "s" if count > 1 else ""
    return f"{count} {carte.noun}{s} {carte.done}{s}"


def progression(lit):
    """Progression pour un nombre donné d'étapes franchies : étapes, total (`TOTAL`) et pourcentage entier."""
    lit = max(0, min(TOTAL, lit or 0))
    return {"lit": lit, "total": TOTAL, "pct": lit * 100 // TOTAL}
