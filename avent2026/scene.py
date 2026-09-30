"""Disposition des 24 jours sur la scène d'accueil.

Volontairement non linéaire : les jours sont répartis dans une grille (avec un léger décalage)
selon une permutation fixe. À remplacer par des coordonnées à la main quand le thème sera choisi.
Coordonnées en % du cadre : (x, y). Deux dispositions : paysage (6x4) et portrait (4x6).
"""
import random


def _layout(cols, rows, seed):
    rng = random.Random(seed)
    days = list(range(1, 25))
    rng.shuffle(days)
    positions = {}
    for index, day in enumerate(days):
        col, row = index % cols, index // cols
        x = (col + 0.5) / cols * 100 + rng.uniform(-3, 3)
        y = (row + 0.5) / rows * 100 + rng.uniform(-3, 3)
        positions[day] = (round(x, 1), round(y, 1))
    return positions


LANDSCAPE = _layout(6, 4, seed=2026)
PORTRAIT = _layout(4, 6, seed=2027)
