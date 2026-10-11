"""Disposition de la scène : 4 zones de 6 jours, avec deux sentiers (voies) par zone.

Chaque zone a deux voies horizontales : énigmes en haut, devinettes en bas. Les 6 jours de la zone sont rangés
de gauche à droite, donc une colonne = un jour (l'énigme au-dessus, la devinette en dessous).

Coordonnées en % du cadre. Deux dispositions : paysage (zones en 2x2) et portrait (zones empilées).
"""

# (nom, description, jours, fond)
ZONES = [
    ("L'Atelier", "Là où tout a commencé : outils, engrenages et vieux plans.", range(1, 7), "#3b2a6b,#1b1446"),
    ("La Décharge", "Des montagnes de pièces détachées à trier pour se réparer.", range(7, 13), "#1f4f5e,#0f2a3a"),
    ("La Forêt gelée", "Sapins givrés, vent glacial, batteries qui ralentissent.", range(13, 19), "#27507a,#0e1f3d"),
    ("Le Pôle Nord", "Les aurores boréales guident les derniers pas.", range(19, 25), "#2f6f63,#14304a"),
]

# Ordre des voies, de haut en bas.
KINDS = ("enigme", "devinette")

# Rectangle (gauche, haut, largeur, hauteur) de chaque zone, en %.
LANDSCAPE_RECTS = [(0, 0, 50, 50), (50, 0, 50, 50), (0, 50, 50, 50), (50, 50, 50, 50)]
PORTRAIT_RECTS = [(0, 0, 100, 25), (0, 25, 100, 25), (0, 50, 100, 25), (0, 75, 100, 25)]

# Position verticale de chaque voie dans sa zone (fraction de la hauteur) : de la place en haut pour le nom de zone.
LANDSCAPE_LANES = (0.5, 0.8)
PORTRAIT_LANES = (0.52, 0.82)

PAD = 0.07  # marge gauche/droite des étapes, en fraction de la largeur de la zone
RAIL_PAD = 0.04  # le rail déborde un peu des étapes extrêmes


def _place(rects, lanes):
    """Position (x, y) de chaque (type, jour)."""
    positions = {}
    for (_name, _desc, days, _bg), (left, top, width, height) in zip(ZONES, rects):
        for col, day in enumerate(days):
            x = left + width * (PAD + (1 - 2 * PAD) * (col + 0.5) / len(days))
            for kind, lane in zip(KINDS, lanes):
                positions[(kind, day)] = (round(x, 1), round(top + height * lane, 1))
    return positions


LANDSCAPE = _place(LANDSCAPE_RECTS, LANDSCAPE_LANES)
PORTRAIT = _place(PORTRAIT_RECTS, PORTRAIT_LANES)


def zone_of(day):
    for index, (_n, _d, days, _bg) in enumerate(ZONES):
        if day in days:
            return index
    raise ValueError(day)


def _rails(index):
    """Les deux rails (un par voie) d'une zone, dans les deux dispositions."""
    (left, top, width, height) = LANDSCAPE_RECTS[index]
    (pleft, ptop, pwidth, pheight) = PORTRAIT_RECTS[index]
    return [
        {"kind": kind,
         "x": round(left + width * RAIL_PAD, 1), "y": round(top + height * lane, 1), "w": round(width * (1 - 2 * RAIL_PAD), 1),
         "px": round(pleft + pwidth * RAIL_PAD, 1), "py": round(ptop + pheight * plane, 1), "pw": round(pwidth * (1 - 2 * RAIL_PAD), 1)}
        for kind, lane, plane in zip(KINDS, LANDSCAPE_LANES, PORTRAIT_LANES)
    ]


def zones_context():
    """Une entrée par zone, avec ses rectangles (paysage/portrait) et ses deux rails."""
    return [
        {"index": i, "name": name, "description": desc, "days": list(days),
         "bg_from": bg.split(",")[0], "bg_to": bg.split(",")[1],
         "rect": LANDSCAPE_RECTS[i], "prect": PORTRAIT_RECTS[i], "rails": _rails(i)}
        for i, (name, desc, days, bg) in enumerate(ZONES)
    ]
