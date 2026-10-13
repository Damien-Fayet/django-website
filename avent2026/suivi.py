"""Suivi staff : connexions, réponses envoyées et temps de réponse (détection de triche).

Le temps de réponse = résolution − premier affichage de la page du puzzle (`Attempt.first_seen_at`).
Un temps très court, ou une réponse envoyée sans avoir jamais ouvert la page, est signalé : c'est un
indice, pas une preuve (quelqu'un peut avoir déjà ouvert l'énigme sur un autre appareil, ou la connaître).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from statistics import median

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Min

from accounts.models import LoginEvent

from .models import Attempt, Submission

SEUIL_DEFAUT = 60  # secondes : en dessous, une résolution est signalée comme « très rapide »


def format_duration(delta):
    """`timedelta` → « 45 s », « 3 min 05 s », « 2 h 10 min », « 1 j 3 h »."""
    if delta is None:
        return "—"
    total = max(0, int(delta.total_seconds()))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    if days:
        return f"{days} j {hours} h"
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {seconds:02d} s"
    return f"{seconds} s"


def _players(include_staff):
    users = get_user_model().objects.all()
    return users if include_staff else users.filter(is_staff=False)


def users_summary(include_staff):
    """Un résumé par compte : connexions suivies, dernière connexion (repli sur `last_login` d'avant le suivi)."""
    users = (_players(include_staff)
             .annotate(logins=Count("login_events"), last_event=Max("login_events__at"))
             .order_by("-last_event", "-last_login", "username"))
    return [{"user": u, "logins": u.logins, "last": u.last_event or u.last_login} for u in users]


def login_events(include_staff, user_id=None):
    qs = LoginEvent.objects.select_related("user").filter(user__in=_players(include_staff))
    return qs.filter(user_id=user_id) if user_id else qs


def shared_ips(include_staff):
    """Adresses IP vues avec plusieurs comptes (connexions ou réponses) : {ip, users}, les plus partagées d'abord.

    Un foyer partage légitimement une IP : c'est un point de départ pour regarder de plus près, pas une preuve.
    """
    players = _players(include_staff)
    pairs = set(LoginEvent.objects.filter(user__in=players, ip__isnull=False)
                .values_list("ip", "user__username").distinct())
    pairs |= set(Submission.objects.filter(user__in=players, ip__isnull=False)
                 .values_list("ip", "user__username").distinct())
    by_ip = {}
    for ip, name in pairs:
        by_ip.setdefault(ip, []).append(name)
    shared = [{"ip": ip, "users": sorted(names)} for ip, names in by_ip.items() if len(names) > 1]
    return sorted(shared, key=lambda r: (-len(r["users"]), r["ip"]))


def submissions(include_staff, user_id=None, puzzle_id=None):
    qs = Submission.objects.select_related("user", "puzzle").filter(user__in=_players(include_staff))
    if user_id:
        qs = qs.filter(user_id=user_id)
    if puzzle_id:
        qs = qs.filter(puzzle_id=puzzle_id)
    return qs


def with_delay(page_rows):
    """Ajoute à chaque réponse le délai depuis le premier affichage du puzzle par ce joueur."""
    keys = {(s.user_id, s.puzzle_id) for s in page_rows}
    seen = {}
    if keys:
        rows = Attempt.objects.filter(user_id__in={k[0] for k in keys}, puzzle_id__in={k[1] for k in keys},
                                      first_seen_at__isnull=False).values_list("user_id", "puzzle_id", "first_seen_at")
        seen = {(u, p): at for u, p, at in rows}
    for s in page_rows:
        first = seen.get((s.user_id, s.puzzle_id))
        s.first_seen = first
        s.delay = format_duration(s.created_at - first) if first and s.created_at >= first else "—"
        s.unseen = first is None
    return page_rows


def response_times(include_staff, seuil, user_id=None, puzzle_id=None, order="rapide"):
    """Une ligne par (joueur, puzzle) ouvert ou répondu, avec durée, signalements et médiane du puzzle."""
    attempts = Attempt.objects.select_related("user", "puzzle").filter(user__in=_players(include_staff))
    if user_id:
        attempts = attempts.filter(user_id=user_id)
    if puzzle_id:
        attempts = attempts.filter(puzzle_id=puzzle_id)
    attempts = list(attempts)

    sub_stats = {
        (r["user_id"], r["puzzle_id"]): r
        for r in Submission.objects.values("user_id", "puzzle_id").annotate(n=Count("id"), first=Min("created_at"))
    }
    rows, by_puzzle = [], {}
    for a in attempts:
        stats = sub_stats.get((a.user_id, a.puzzle_id))
        n_sub = stats["n"] if stats else 0
        duration = a.solved_at - a.first_seen_at if a.solved_at and a.first_seen_at else None
        flags = []
        if duration is not None and duration.total_seconds() < seuil:
            flags.append(f"Résolu en moins de {seuil} s après l'affichage")
        if a.first_seen_at is None and n_sub:
            flags.append("Réponse envoyée sans avoir ouvert la page")
        row = {
            "attempt": a, "user": a.user, "puzzle": a.puzzle, "n_sub": n_sub, "duration": duration,
            "duration_text": format_duration(duration), "flags": flags,
            "first_answer": (stats["first"] - a.first_seen_at) if stats and a.first_seen_at else None,
        }
        row["first_answer_text"] = format_duration(row["first_answer"])
        rows.append(row)
        if duration is not None:
            by_puzzle.setdefault(a.puzzle_id, []).append(duration.total_seconds())
    medians = {pid: median(v) for pid, v in by_puzzle.items()}
    for row in rows:
        m = medians.get(row["puzzle"].id)
        row["median_text"] = format_duration(timedelta(seconds=m)) if m is not None else "—"

    if order == "recent":
        oldest = datetime.min.replace(tzinfo=dt_timezone.utc)
        rows.sort(key=lambda r: r["attempt"].solved_at or r["attempt"].first_seen_at or oldest, reverse=True)
    else:  # les plus rapides d'abord ; les non résolus (ou sans durée connue) à la fin
        rows.sort(key=lambda r: (r["duration"] is None, r["duration"].total_seconds() if r["duration"] is not None else 0, r["user"].username))
    return rows

