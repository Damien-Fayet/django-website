"""Disposition de la scène : 4 zones de 6 jours, jours mélangés à l'intérieur de chaque zone.

Coordonnées en % du cadre. Deux dispositions : paysage (zones en 2x2) et portrait (zones empilées).
À ajuster à la main quand le décor sera dessiné.
"""
import random

# (nom, description, jours, fond)
ZONES = [
    ("L'Atelier", "Là où tout a commencé : outils, engrenages et vieux plans.", range(1, 7), "#3b2a6b,#1b1446"),
    ("La Décharge", "Des montagnes de pièces détachées à trier pour se réparer.", range(7, 13), "#1f4f5e,#0f2a3a"),
    ("La Forêt gelée", "Sapins givrés, vent glacial, batteries qui ralentissent.", range(13, 19), "#27507a,#0e1f3d"),
    ("Le Pôle Nord", "Les aurores boréales guident les derniers pas.", range(19, 25), "#2f6f63,#14304a"),
]

# Rectangle (gauche, haut, largeur, hauteur) de chaque zone, en %.
LANDSCAPE_RECTS = [(0, 0, 50, 50), (50, 0, 50, 50), (0, 50, 50, 50), (50, 50, 50, 50)]
PORTRAIT_RECTS = [(0, 0, 100, 25), (0, 25, 100, 25), (0, 50, 100, 25), (0, 75, 100, 25)]


def _place(rects, cols, rows, seed):
    rng = random.Random(seed)
    positions = {}
    for (_name, _desc, days, _bg), (left, top, width, height) in zip(ZONES, rects):
        days = list(days)
        rng.shuffle(days)
        for index, day in enumerate(days):
            col, row = index % cols, index // cols
            x = left + (col + 0.5) / cols * width + rng.uniform(-2, 2)
            y = top + (0.2 + 0.76 * (row + 0.5) / rows) * height + rng.uniform(-1.5, 1.5)  # marge en haut pour le nom de zone
            positions[day] = (round(x, 1), round(y, 1))
    return positions


LANDSCAPE = _place(LANDSCAPE_RECTS, cols=3, rows=2, seed=2026)
PORTRAIT = _place(PORTRAIT_RECTS, cols=3, rows=2, seed=2027)


def zone_of(day):
    for index, (_n, _d, days, _bg) in enumerate(ZONES):
        if day in days:
            return index
    raise ValueError(day)


def zones_context():
    """Une entrée par zone, avec ses rectangles (paysage/portrait)."""
    return [
        {"index": i, "name": name, "description": desc, "days": list(days),
         "bg_from": bg.split(",")[0], "bg_to": bg.split(",")[1],
         "rect": LANDSCAPE_RECTS[i], "prect": PORTRAIT_RECTS[i]}
        for i, (name, desc, days, bg) in enumerate(ZONES)
    ]
