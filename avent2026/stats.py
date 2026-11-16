"""Page « Statistiques » : ce que le jeu dit de toi, de chaque puzzle et de l'ensemble des joueurs.

Tout est calculé à la demande depuis `Attempt`, `HintReveal`, `Submission`, `LeaderboardDay` et `accounts.LoginEvent`
(aucune table de plus). Le staff joue pour tester : il est exclu de toutes les statistiques communes, comme au
classement ; ses propres chiffres restent visibles dans « Mes statistiques ».

Temps de résolution = résolution − premier affichage de la page du puzzle (`Attempt.first_seen_at`), pauses comprises :
quelqu'un qui ouvre l'énigme le matin et la résout le soir a un temps de plusieurs heures. La médiane est donc la
mesure la plus parlante, la moyenne est donnée à côté. Seuls les puzzles dont le premier affichage est connu comptent.

Rien de nominatif ici : uniquement des totaux, des moyennes et des médianes (les noms des premiers sont déjà au
classement).
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from statistics import mean, median

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from accounts.models import LoginEvent

from . import achievements, scoring, suivi, village
from .models import Attempt, HintReveal, LeaderboardDay, Puzzle, Submission

MIN_SOLVERS = 3  # en dessous, pas de « record » : trois résolutions au moins pour qu'une moyenne veuille dire quelque chose
PODIUM_PLACES = len(scoring.PODIUM_BONUS)
MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
KIND_LABELS = {"enigme": "Énigmes", "devinette": "Devinettes"}
_FIELDS = ("user_id", "puzzle_id", "errors", "solved_at", "first_seen_at", "points", "rank")


# ---- Mise en forme ---------------------------------------------------------------------------------------------

def duration_text(seconds):
    """Secondes → « 3 min 05 s » ; « — » quand on ne sait pas."""
    return "—" if seconds is None else suivi.format_duration(timedelta(seconds=seconds))


def num(value, digits=1):
    """Nombre décimal à la française (« 1,5 »), « — » quand il n'y a rien à moyenner."""
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def pct(part, whole):
    """Pourcentage arrondi, None quand le total est nul."""
    return round(100 * part / whole) if whole else None


def pct_text(part, whole):
    value = pct(part, whole)
    return "—" if value is None else f"{value} %"


def plural(n, word, plural_form=None):
    return f"{n} {word if n < 2 else (plural_form or word + 's')}"


# ---- Données brutes --------------------------------------------------------------------------------------------

def _seconds(row):
    """Temps de résolution en secondes, None s'il est inconnu (non résolu, ou premier affichage non enregistré)."""
    if row["solved_at"] and row["first_seen_at"]:
        seconds = (row["solved_at"] - row["first_seen_at"]).total_seconds()
        return seconds if seconds >= 0 else None
    return None


def _hint_counts(**filters):
    qs = HintReveal.objects.filter(**filters).values("user_id", "hint__puzzle_id").annotate(n=Count("id"))
    return {(r["user_id"], r["hint__puzzle_id"]): r["n"] for r in qs}


def _enrich(rows, hints, puzzles):
    for row in rows:
        row["hints"] = hints.get((row["user_id"], row["puzzle_id"]), 0)
        row["seconds"] = _seconds(row)
        row["kind"] = puzzles[row["puzzle_id"]].kind
    return rows


def all_puzzles():
    """{id: Puzzle} (champs légers) : un seul accès à la base pour toute la page."""
    return {p.id: p for p in Puzzle.objects.only("id", "kind", "day", "title", "unlock_date")}


def community_attempts(puzzles):
    """Une ligne par (joueur, puzzle) ouvert, hors staff."""
    rows = list(Attempt.objects.filter(user__is_staff=False).values(*_FIELDS))
    return _enrich(rows, _hint_counts(user__is_staff=False), puzzles)


def user_attempts(user, puzzles):
    rows = list(Attempt.objects.filter(user=user).values(*_FIELDS))
    return _enrich(rows, _hint_counts(user=user), puzzles)


def metrics(rows, puzzles):
    """Résumé d'un ensemble de (joueur, puzzle) : résolutions, points, erreurs, indices, temps."""
    solved = [r for r in rows if r["solved_at"]]
    timed = [r for r in solved if r["seconds"] is not None]
    seconds = [r["seconds"] for r in timed]
    n = len(solved)
    fastest = min(timed, key=lambda r: r["seconds"]) if timed else None
    slowest = max(timed, key=lambda r: r["seconds"]) if timed else None
    return {
        "opened": len(rows), "solved": n, "points": sum(r["points"] for r in solved),
        "errors_total": sum(r["errors"] for r in rows), "hints_total": sum(r["hints"] for r in rows),
        "errors_avg": sum(r["errors"] for r in solved) / n if n else None,
        "hints_avg": sum(r["hints"] for r in solved) / n if n else None,
        "first_try": sum(1 for r in solved if r["errors"] == 0),
        "no_hint": sum(1 for r in solved if r["hints"] == 0),
        "median": median(seconds) if seconds else None, "mean": mean(seconds) if seconds else None,
        "fastest": (puzzles[fastest["puzzle_id"]].title, fastest["seconds"]) if fastest else None,
        "slowest": (puzzles[slowest["puzzle_id"]].title, slowest["seconds"]) if slowest else None,
    }


# ---- Onglet « Mes statistiques » -------------------------------------------------------------------------------

def _versus(mine, theirs, fmt):
    return f"Tous les joueurs : {fmt(theirs)}" if theirs is not None and mine is not None else ""


def personal(user, visible, community, puzzles):
    """Cartes et détail par piste du joueur, comparés à la moyenne des autres. `visible` : puzzles déjà sortis."""
    mine_rows = user_attempts(user, puzzles)
    me, ref = metrics(mine_rows, puzzles), metrics(community, puzzles)
    published = Counter(p.kind for p in visible)

    # Place au classement général (mêmes règles : points, ex æquo à la même place, hors staff).
    totals = defaultdict(int)
    for r in community:
        if r["solved_at"]:
            totals[r["user_id"]] += r["points"]
    place = None
    if me["solved"] and not user.is_staff:
        place = 1 + sum(1 for points in totals.values() if points > me["points"])
    if place:
        place_text = f"{'1er' if place == 1 else str(place) + 'e'} sur {plural(len(totals), 'joueur')}"
    else:
        place_text = "Le staff n'est pas classé" if user.is_staff else "Résous un puzzle pour entrer au classement"
    podiums = sum(1 for r in mine_rows if r["solved_at"] and r["rank"] and r["rank"] <= PODIUM_PLACES)
    faits = len(achievements.keys_for(user))

    total_published = sum(published.values())
    cards = [
        {"label": "Puzzles résolus", "value": f"{me['solved']} / {total_published}",
         "sub": f"{pct_text(me['solved'], total_published)} de ce qui est sorti"},
        {"label": "Points", "value": str(me["points"]), "sub": place_text},
        {"label": "Temps médian de résolution", "value": duration_text(me["median"]),
         "sub": _versus(me["median"], ref["median"], duration_text)},
        {"label": "Temps moyen de résolution", "value": duration_text(me["mean"]),
         "sub": _versus(me["mean"], ref["mean"], duration_text)},
        {"label": "Erreurs par puzzle résolu", "value": num(me["errors_avg"]),
         "sub": _versus(me["errors_avg"], ref["errors_avg"], num) or f"{plural(me['errors_total'], 'erreur')} en tout"},
        {"label": "Indices par puzzle résolu", "value": num(me["hints_avg"]),
         "sub": _versus(me["hints_avg"], ref["hints_avg"], num) or f"{plural(me['hints_total'], 'indice')} pris en tout"},
        {"label": "Du premier coup", "value": str(me["first_try"]),
         "sub": f"{pct_text(me['first_try'], me['solved'])} de tes résolutions"},
        {"label": "Sans indice", "value": str(me["no_hint"]),
         "sub": f"{pct_text(me['no_hint'], me['solved'])} de tes résolutions"},
        {"label": "Podiums", "value": str(podiums),
         "sub": f"Dans les {PODIUM_PLACES} premiers à briser un verrou"},
        {"label": "Hauts-faits", "value": f"{faits} / {len(achievements.HAUTS_FAITS)}", "sub": "Voir lesquels au classement"},
    ]

    kinds = []
    for kind, label in KIND_LABELS.items():
        k = metrics([r for r in mine_rows if r["kind"] == kind], puzzles)
        carte = village.CARTES[kind]
        facts = [
            ("Résolues", f"{k['solved']} sur {published[kind]} sorties ({len(carte.days)} au total)"),
            ("Points", str(k["points"])),
            ("Erreurs", f"{k['errors_total']} en tout, {num(k['errors_avg'])} par puzzle résolu"),
            ("Indices pris", f"{k['hints_total']} en tout, {num(k['hints_avg'])} par puzzle résolu"),
            ("Du premier coup", f"{k['first_try']} sur {k['solved']}"),
            ("Sans indice", f"{k['no_hint']} sur {k['solved']}"),
            ("Temps médian", duration_text(k["median"])),
            ("Temps moyen", duration_text(k["mean"])),
            ("Plus rapide", f"{k['fastest'][0]}, {duration_text(k['fastest'][1])}" if k["fastest"] else "—"),
            ("Plus long", f"{k['slowest'][0]}, {duration_text(k['slowest'][1])}" if k["slowest"] else "—"),
        ]
        kinds.append({"name": carte.name, "label": label, "facts": facts})
    return {"cards": cards, "kinds": kinds, "empty": not me["opened"]}


# ---- Onglet « Puzzle par puzzle » ------------------------------------------------------------------------------

def _records(rows):
    """Les puzzles qui se détachent (au moins MIN_SOLVERS résolutions) : plus coriace, plus rapide, plus long, plus d'indices."""
    eligible = [r for r in rows if r["solvers"] >= MIN_SOLVERS]
    out = []

    def best(label, key, value_text, reverse=True, minimum=0):
        candidates = [r for r in eligible if r[key] is not None and r[key] > minimum] if reverse else \
                     [r for r in eligible if r[key] is not None]
        if candidates:
            pick = (max if reverse else min)(candidates, key=lambda r: r[key])
            out.append({"label": label, "title": pick["puzzle"].title, "value": value_text(pick)})

    best("Le plus coriace", "errors_avg", lambda r: f"{num(r['errors_avg'])} erreurs en moyenne")
    best("Le plus rapide", "median", lambda r: f"{duration_text(r['median'])} en médiane", reverse=False)
    best("Le plus long", "median", lambda r: f"{duration_text(r['median'])} en médiane")
    best("Celui qui demande le plus d'indices", "hints_avg", lambda r: f"{num(r['hints_avg'])} indices en moyenne")
    return out


def puzzle_tables(visible, community, mine, puzzles):
    """Un tableau par piste, avec les chiffres de tous les joueurs et la ligne « toi »."""
    by_puzzle = defaultdict(list)
    for r in community:
        by_puzzle[r["puzzle_id"]].append(r)
    mine_by = {r["puzzle_id"]: r for r in mine}
    tables = []
    for kind, label in KIND_LABELS.items():
        rows = []
        for p in (p for p in visible if p.kind == kind):
            m = metrics(by_puzzle.get(p.id, []), puzzles)
            mine_row = mine_by.get(p.id)
            if mine_row is None:
                you = {"state": "todo"}
            elif mine_row["solved_at"]:
                you = {"state": "done", "time": duration_text(mine_row["seconds"]), "errors": mine_row["errors"],
                       "hints": mine_row["hints"], "points": mine_row["points"]}
            else:
                you = {"state": "open", "errors": mine_row["errors"], "hints": mine_row["hints"]}
            rows.append({
                "puzzle": p, "step": village.CARTES[kind].days.index(p.day) + 1 if p.day in village.CARTES[kind].days else None,
                "opened": m["opened"], "solvers": m["solved"], "success": pct_text(m["solved"], m["opened"]),
                "median": m["median"], "median_text": duration_text(m["median"]),
                "mean_text": duration_text(m["mean"]),
                "errors_avg": m["errors_avg"], "errors_text": num(m["errors_avg"]),
                "hints_avg": m["hints_avg"], "hints_text": num(m["hints_avg"]),
                "first_try": pct_text(m["first_try"], m["solved"]), "no_hint": pct_text(m["no_hint"], m["solved"]),
                "you": you,
            })
        tables.append({"kind": kind, "name": village.CARTES[kind].name, "label": label, "rows": rows,
                       "records": _records(rows)})
    return tables


# ---- Onglet « Tous les joueurs » -------------------------------------------------------------------------------

def _active_ids(since):
    """Joueurs (hors staff) qui ont fait quelque chose depuis `since` : réponse, puzzle ouvert, indice, classement, connexion."""
    ids = set()
    sources = (
        (Submission.objects, {"created_at__gte": since}), (Attempt.objects, {"first_seen_at__gte": since}),
        (Attempt.objects, {"solved_at__gte": since}), (HintReveal.objects, {"revealed_at__gte": since}),
        (LeaderboardDay.objects, {"day__gte": since.date()}), (LoginEvent.objects, {"at__gte": since}),
    )
    for manager, condition in sources:
        ids.update(manager.filter(user__is_staff=False, **condition).values_list("user_id", flat=True))
    return ids


def _bars(counts, labels):
    """[(libellé, nombre)] → barres {label, count, pct} : `pct` relatif à la plus haute (entier, sans virgule dans le CSS)."""
    peak = max(counts) if counts else 0
    return [{"label": label, "count": count, "pct": round(100 * count / peak) if peak else 0}
            for label, count in zip(labels, counts)]


def site(community, puzzles):
    """Chiffres de l'ensemble des joueurs (hors staff) : participation, activité, résolutions, quand on joue."""
    User = get_user_model()
    non_staff = User.objects.filter(is_staff=False)
    registered = non_staff.count()
    opened = {r["user_id"] for r in community}
    solvers = {r["user_id"] for r in community if r["solved_at"]}
    # « Visiteurs uniques » : comptes venus au moins une fois (connexion, puzzle ouvert ou classement consulté).
    # Les visiteurs sans compte ne sont pas comptés : la page d'accueil publique ne les enregistre pas.
    visitors = (set(non_staff.filter(last_login__isnull=False).values_list("pk", flat=True))
                | set(LoginEvent.objects.filter(user__is_staff=False).values_list("user_id", flat=True))
                | set(LeaderboardDay.objects.filter(user__is_staff=False).values_list("user_id", flat=True))
                | opened)

    now = scoring.now()
    today_start = datetime.combine(now.date(), time.min, tzinfo=scoring.TZ)
    answers = Submission.objects.filter(user__is_staff=False).aggregate(
        total=Count("id"), good=Count("id", filter=Q(correct=True)))
    hint_reveals = HintReveal.objects.filter(user__is_staff=False).count()
    overall = metrics(community, puzzles)

    per_kind_done = defaultdict(Counter)  # {kind: {user_id: puzzles résolus}}
    for r in community:
        if r["solved_at"]:
            per_kind_done[r["kind"]][r["user_id"]] += 1
    finished = {kind: sum(1 for n in per_kind_done[kind].values() if n >= len(village.CARTES[kind].days))
                for kind in KIND_LABELS}

    solved_rows = [r for r in community if r["solved_at"]]
    local = [r["solved_at"].astimezone(scoring.TZ) for r in solved_rows]
    per_day = Counter(d.date() for d in local)
    per_hour = Counter(d.hour for d in local)
    days = []
    if per_day:
        first, last = min(per_day), max(per_day)
        days = [first + timedelta(n) for n in range((last - first).days + 1)]
    by_day = _bars([per_day[d] for d in days], [f"{d.day} {MOIS[d.month - 1]}" for d in days])
    by_hour = _bars([per_hour[h] for h in range(24)], [f"{h} h" for h in range(24)])
    busiest_hour = max(range(24), key=lambda h: (per_hour[h], -h)) if per_hour else None
    busiest_day = max(days, key=lambda d: (per_day[d], d)) if days else None

    def kind_row(kind):
        k = metrics([r for r in community if r["kind"] == kind], puzzles)
        return {"name": KIND_LABELS[kind], "solved": k["solved"], "opened": k["opened"],
                "success": pct_text(k["solved"], k["opened"]), "median": duration_text(k["median"]),
                "errors": num(k["errors_avg"]), "hints": num(k["hints_avg"]),
                "first_try": pct_text(k["first_try"], k["solved"]), "no_hint": pct_text(k["no_hint"], k["solved"])}

    cards = [
        {"label": "Comptes inscrits", "value": str(registered), "sub": "Hors comptes staff"},
        {"label": "Visiteurs uniques", "value": str(len(visitors)),
         "sub": "Comptes venus au moins une fois (sans compte : non comptés)"},
        {"label": "Joueurs", "value": str(len(opened)), "sub": f"Ont ouvert au moins un puzzle, dont {len(solvers)} en ont résolu un"},
        {"label": "Actifs aujourd'hui", "value": str(len(_active_ids(today_start))), "sub": "Depuis minuit, heure de Paris"},
        {"label": "Actifs sur 7 jours", "value": str(len(_active_ids(today_start - timedelta(days=6)))),
         "sub": "Aujourd'hui compris"},
        {"label": "Puzzles résolus", "value": str(overall["solved"]), "sub": f"{overall['points']} points distribués"},
        {"label": "Réponses envoyées", "value": str(answers["total"] or 0),
         "sub": f"{pct_text(answers['good'] or 0, answers['total'])} de bonnes réponses"},
        {"label": "Erreurs", "value": str(overall["errors_total"]),
         "sub": f"{num(overall['errors_avg'])} par puzzle résolu en moyenne"},
        {"label": "Indices révélés", "value": str(hint_reveals),
         "sub": f"{pct_text(overall['no_hint'], overall['solved'])} des résolutions sans indice"},
        {"label": "Temps médian de résolution", "value": duration_text(overall["median"]),
         "sub": f"Temps moyen : {duration_text(overall['mean'])}"},
        {"label": "Ont brisé les 8 verrous", "value": str(finished["enigme"]), "sub": "La cellule est vide"},
        {"label": "Ont rallumé tout le village", "value": str(finished["devinette"]), "sub": f"Les {village.DAYS} devinettes résolues"},
    ]
    return {
        "cards": cards, "kind_rows": [kind_row(k) for k in KIND_LABELS], "by_day": by_day, "by_hour": by_hour,
        "busiest_hour": busiest_hour, "busiest_day": f"{busiest_day.day} {MOIS[busiest_day.month - 1]}" if busiest_day else None,
        "has_resolutions": bool(solved_rows),
    }
