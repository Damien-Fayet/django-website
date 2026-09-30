"""Le petit robot : niveaux, modules et histoire. Données pures, faciles à modifier."""

# (seuil d'énergie = total des points, clé du module, nom affiché, description)
LEVELS = [
    (0,    None,       "Prototype",        "Un petit robot tout juste sorti de l'atelier. Il ne sait encore presque rien faire."),
    (300,  "antenna",   "Antenne radio",    "Il capte enfin un signal lointain… une voix chaleureuse ?"),
    (900,  "arms",      "Bras articulés",   "Il peut attraper des objets et actionner des leviers."),
    (2000, "wheels",    "Chenilles renforcées", "Plus rien ne l'arrête sur la glace."),
    (3500, "radar",     "Radar",            "Il repère les obstacles avant de les heurter."),
    (5500, "jetpack",   "Jetpack",          "Prêt à décoller vers le Pôle Nord !"),
]

PROLOGUE = (
    "Dans un coin poussiéreux de l'atelier, un petit robot vient de s'allumer. "
    "Un signal étrange crépite dans son circuit : « … prêt pour la tournée… j'ai besoin d'aide… » "
    "C'est le Père Noël ! Mais le Pôle Nord est loin, et le robot ne sait presque rien faire. "
    "À vous de l'aider à apprendre, à se réparer et à s'améliorer, jour après jour, pour qu'il arrive à temps."
)

EPILOGUE = (
    "Le robot franchit la dernière congère et pousse la porte du chalet. "
    "Le Père Noël l'attend, un chocolat chaud à la main : « Je savais que tu y arriverais. »"
)


def robot_state(energy):
    """État du robot pour un total d'énergie (points) donné."""
    energy = max(0, energy or 0)
    level = 0
    for index, (threshold, *_rest) in enumerate(LEVELS):
        if energy >= threshold:
            level = index
    modules = [{"key": key, "name": name, "description": desc}
               for threshold, key, name, desc in LEVELS[1:level + 1]]
    next_threshold = LEVELS[level + 1][0] if level + 1 < len(LEVELS) else None
    if next_threshold is None:
        progress = 100
    else:
        start = LEVELS[level][0]
        progress = int((energy - start) * 100 / (next_threshold - start))
    return {
        "energy": energy,
        "level": level + 1,
        "max_level": len(LEVELS),
        "title": LEVELS[level][2],
        "description": LEVELS[level][3],
        "modules": modules,
        "module_keys": [m["key"] for m in modules],
        "next_threshold": next_threshold,
        "next_module": LEVELS[level + 1][2] if next_threshold is not None else None,
        "progress_pct": progress,
    }
