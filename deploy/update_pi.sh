#!/usr/bin/env bash
# =============================================================================
# update_pi.sh — met à jour le site « avent » depuis origin/main (Raspberry Pi)
#
# Lancé toutes les quelques minutes par le timer systemd `avent-update.timer`
# (voir deploy/install_autoupdate.sh). Ne fait rien s'il n'y a rien de nouveau.
# Sinon : sauvegarde de la base, fast-forward du dépôt, dépendances si besoin,
# check, migrate, collectstatic, redémarrage du service, puis contrôle HTTP.
# En cas d'échec : retour au commit précédent et le commit fautif est mémorisé
# (aucune boucle de redémarrages) jusqu'à l'arrivée d'un nouveau commit.
#
# Usage :  bash update_pi.sh [options]
#   --check    indique les commits en attente, ne modifie rien
#   --retry    retente même si ce commit a déjà échoué
#   --help     cette aide
#
# Variables d'environnement utiles : APP_DIR (défaut /srv/siteAvent), BRANCH
# (défaut main), SERVICE_NAME (défaut avent), KEEP_BACKUPS (défaut 10).
# Suivi : journalctl -u avent-update -n 50   et   cat $APP_DIR/last_deploy.txt
# =============================================================================
set -Eeuo pipefail

# ---------- Configuration (surchargeable par l'environnement) -----------------
APP_DIR="${APP_DIR:-/srv/siteAvent}"
PROJECT_DIR="${PROJECT_DIR:-$APP_DIR/django-website}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
SERVICE_NAME="${SERVICE_NAME:-avent}"
ENV_FILE="${ENV_FILE:-/etc/avent.env}"
BRANCH="${BRANCH:-main}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"
WAIT_HTTP="${WAIT_HTTP:-60}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/accounts/login/}"
SUDO="${SUDO-sudo}"                       # SUDO="" pour les tests sans droits root
# Chemin absolu : doit correspondre exactement à la règle sudo (install_autoupdate.sh).
SYSTEMCTL="${SYSTEMCTL:-$(command -v systemctl || echo /usr/bin/systemctl)}"

LOCK_FILE="$APP_DIR/.update.lock"
FAILED_FILE="$APP_DIR/.update_failed"     # sha du dernier commit distant en échec
STATUS_FILE="$APP_DIR/last_deploy.txt"    # une ligne : date, résultat, commit

CHECK_ONLY=0; RETRY=0

# État de l'exécution (utilisé par le nettoyage en cas d'échec).
PREV_SHA=""; NEW_SHA=""; MERGED=0; RESTARTED=0; COLLECTED=0; REQ_CHANGED=0; CLEANED=0

log()  { printf '%s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*" >&2; }

write_status() { # write_status résultat [détail]
  printf '%s  %s  %s %s\n' "$(date '+%F %T')" "$1" "${NEW_SHA:0:7}" "${2:-}" >"$STATUS_FILE" 2>/dev/null || true
}

git_() { git -C "$PROJECT_DIR" "$@"; }

restart_service() {
  if [[ -n "$SUDO" ]]; then $SUDO -n "$SYSTEMCTL" restart "$SERVICE_NAME"; else "$SYSTEMCTL" restart "$SERVICE_NAME"; fi
}

# Les commandes manage.py ont besoin de DJANGO_SECRET_KEY : fournie par systemd
# (EnvironmentFile) ; en lancement manuel, relue depuis le fichier root.
load_env() {
  [[ -n "${DJANGO_SECRET_KEY:-}" ]] && return 0
  [[ -n "$SUDO" ]] || return 0
  set -a; source <($SUDO cat "$ENV_FILE"); set +a
}

# Pas de sous-shell ici : le piège ERR hérité y déclencherait deux fois le nettoyage.
manage() { "$VENV_DIR/bin/python" "$PROJECT_DIR/manage.py" "$@"; }

backup_db() {
  local db="$PROJECT_DIR/db.sqlite3" out
  [[ -f "$db" ]] || { log "Pas de base à sauvegarder."; return 0; }
  mkdir -p "$BACKUP_DIR"
  out="$BACKUP_DIR/pre-deploy-$(date +%Y%m%d-%H%M%S)-${NEW_SHA:0:7}.sqlite3"
  # API de sauvegarde SQLite : copie cohérente même si le site écrit en même temps.
  "$VENV_DIR/bin/python" - "$db" "$out" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
dst.close(); src.close()
PY
  log "Base sauvegardée : $out"
  # Rotation : on garde les KEEP_BACKUPS dernières sauvegardes « pre-deploy ».
  # shellcheck disable=SC2012
  ls -1t "$BACKUP_DIR"/pre-deploy-*.sqlite3 2>/dev/null | tail -n +"$((KEEP_BACKUPS + 1))" | xargs -r rm -f
}

wait_for_site() {
  local domain code="" waited=0
  domain="$(cat "$APP_DIR/.domain" 2>/dev/null || true)"
  if [[ -z "$domain" && -z "${HEALTH_HOST:-}" ]]; then
    # Domaine inconnu (ALLOWED_HOSTS refuserait une requête locale) : on se contente de l'état du service.
    sleep 5
    "$SYSTEMCTL" is-active --quiet "$SERVICE_NAME"
    return
  fi
  domain="${HEALTH_HOST:-$domain}"
  while [[ $waited -lt $WAIT_HTTP ]]; do
    code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H "Host: $domain" "$HEALTH_URL" || true)"
    [[ "$code" == "200" ]] && return 0
    sleep 3; waited=$((waited + 3))
  done
  log "Dernier code HTTP reçu : ${code:-aucun}"
  return 1
}

# Retour à l'état précédent ; mémorise le commit fautif pour ne pas boucler.
cleanup_failure() { # cleanup_failure message
  [[ $CLEANED -eq 0 ]] || return 0
  CLEANED=1
  trap - ERR
  warn "ÉCHEC : $1"
  if [[ $MERGED -eq 1 && -n "$PREV_SHA" ]]; then
    warn "Retour au commit ${PREV_SHA:0:7}."
    git_ reset --keep "$PREV_SHA" >&2 || warn "Retour en arrière impossible : vérifiez le dépôt à la main."
    if [[ $REQ_CHANGED -eq 1 ]]; then
      "$VENV_DIR/bin/pip" install --disable-pip-version-check -q -r "$PROJECT_DIR/requirements.txt" >&2 || true
    fi
    if [[ $COLLECTED -eq 1 ]]; then manage collectstatic --noinput >/dev/null 2>&1 || true; fi
    if [[ $RESTARTED -eq 1 ]]; then restart_service >&2 || warn "Redémarrage du service impossible."; fi
    warn "Les migrations déjà appliquées ne sont pas annulées : sauvegarde dans $BACKUP_DIR."
  fi
  [[ -n "$NEW_SHA" ]] && echo "$NEW_SHA" >"$FAILED_FILE"
  write_status "ECHEC" "$1"
}

die() { cleanup_failure "$*"; exit 1; }

on_error() { cleanup_failure "commande en échec (ligne $1, code $2)"; exit "$2"; }

usage() { sed -n '2,/^# =====*$/p' "$0" | sed 's/^# \{0,1\}//' | head -n 24; }

# Tout le corps est dans une fonction : bash lit le script en entier avant de
# l'exécuter, ce qui évite qu'un `git merge` qui remplace ce fichier en cours
# d'exécution ne corrompe la suite du script.
main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --check) CHECK_ONLY=1 ;;
      --retry) RETRY=1 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Option inconnue : $1" >&2; usage; exit 2 ;;
    esac
    shift
  done

  [[ -d "$PROJECT_DIR/.git" ]] || { echo "Dépôt introuvable : $PROJECT_DIR" >&2; exit 1; }
  cd "$PROJECT_DIR"   # manage.py s'attend à tourner depuis la racine du projet

  # Un seul déploiement à la fois (timer + lancement manuel).
  exec 9>"$LOCK_FILE"
  flock -n 9 || { log "Une mise à jour est déjà en cours."; exit 0; }

  # Réseau indisponible : on réessaiera au prochain passage, ce n'est pas une erreur.
  if ! timeout 90 git -C "$PROJECT_DIR" fetch --quiet origin "$BRANCH"; then
    warn "git fetch impossible (réseau ?) : nouvel essai au prochain passage."
    exit 0
  fi

  PREV_SHA="$(git_ rev-parse HEAD)"
  NEW_SHA="$(git_ rev-parse "origin/$BRANCH")"

  if [[ "$PREV_SHA" == "$NEW_SHA" ]]; then
    [[ $CHECK_ONLY -eq 0 ]] || log "Déjà à jour (${PREV_SHA:0:7})."
    [[ $RETRY -eq 0 ]] || rm -f "$FAILED_FILE"
    exit 0
  fi

  if [[ $CHECK_ONLY -eq 1 ]]; then
    log "Mise à jour disponible : ${PREV_SHA:0:7} -> ${NEW_SHA:0:7}"
    git_ log --oneline --no-decorate "$PREV_SHA..$NEW_SHA" || true
    exit 0
  fi

  if [[ $RETRY -eq 0 && -f "$FAILED_FILE" && "$(cat "$FAILED_FILE")" == "$NEW_SHA" ]]; then
    log "Le commit ${NEW_SHA:0:7} a déjà échoué : en attente d'un nouveau commit (ou --retry)."
    exit 0
  fi

  trap 'on_error $LINENO $?' ERR
  log "Mise à jour ${PREV_SHA:0:7} -> ${NEW_SHA:0:7}"
  git_ log --oneline --no-decorate "$PREV_SHA..$NEW_SHA" || true

  # settings.py porte la configuration de production en local (skip-worktree) :
  # si le dépôt le modifie, une mise à jour automatique l'écraserait ou échouerait.
  if ! git_ diff --quiet "$PREV_SHA" "$NEW_SHA" -- mysite/settings.py; then
    die "mysite/settings.py est modifié par ce commit : mise à jour à faire à la main (voir DEPLOY_PI.md)."
  fi

  # Fichiers modifiés avant fusion (pour décider des dépendances à réinstaller).
  git_ diff --name-only "$PREV_SHA" "$NEW_SHA" | grep -qx 'requirements.txt' && REQ_CHANGED=1 || true

  load_env
  backup_db

  git_ merge --ff-only --quiet "$NEW_SHA" || die "fusion impossible (historique réécrit ou fichiers modifiés localement ?)."
  MERGED=1

  if [[ $REQ_CHANGED -eq 1 ]]; then
    log "requirements.txt modifié : installation des dépendances…"
    "$VENV_DIR/bin/pip" install --disable-pip-version-check -q -r "$PROJECT_DIR/requirements.txt"
  fi

  manage check
  manage migrate --noinput
  manage collectstatic --noinput >/dev/null
  COLLECTED=1

  restart_service
  RESTARTED=1
  wait_for_site || die "le site ne répond pas après le redémarrage."

  rm -f "$FAILED_FILE"
  write_status "OK"
  log "Site mis à jour : ${NEW_SHA:0:7}."
}

main "$@"; exit $?
