#!/usr/bin/env bash
# =============================================================================
# install_autoupdate.sh — active la mise à jour automatique du site sur le Pi
#
# Installe un timer systemd qui lance deploy/update_pi.sh toutes les N minutes :
# dès qu'un commit arrive sur origin/main, le site est mis à jour (sauvegarde de
# la base, migrate, collectstatic, redémarrage, contrôle, retour arrière si échec).
#
# Usage :  bash deploy/install_autoupdate.sh [options]
#   --interval N   minutes entre deux vérifications (défaut 5)
#   --dry-run      affiche les fichiers qui seraient installés, ne modifie rien
#   --uninstall    retire le timer, le service et la règle sudo
#   --help         cette aide
#
# Ne lancez PAS ce script avec sudo : il l'appelle lui-même quand il le faut.
# Variables : APP_DIR (défaut /srv/siteAvent), SERVICE_NAME (défaut avent).
# =============================================================================
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/srv/siteAvent}"
PROJECT_DIR="${PROJECT_DIR:-$APP_DIR/django-website}"
SERVICE_NAME="${SERVICE_NAME:-avent}"
ENV_FILE="${ENV_FILE:-/etc/avent.env}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SUDOERS_DIR="${SUDOERS_DIR:-/etc/sudoers.d}"
SUDO="${SUDO-sudo}"                         # SUDO="" pour les tests sans droits root
SYSTEMCTL="${SYSTEMCTL:-$(command -v systemctl || echo /usr/bin/systemctl)}"
USER="${USER:-$(id -un)}"

UNIT="${SERVICE_NAME}-update"
INTERVAL=5; DRY_RUN=0; UNINSTALL=0; TMP_SUDOERS=""

die() { printf '✘ %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }

# ---------- Fichiers générés (fonctions pures) --------------------------------
render_service() {
  cat <<EOF
[Unit]
Description=Mise à jour automatique du site $SERVICE_NAME (git, migrate, redémarrage)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
Environment=APP_DIR=$APP_DIR
Environment=SERVICE_NAME=$SERVICE_NAME
Environment=ENV_FILE=$ENV_FILE
Environment=SYSTEMCTL=$SYSTEMCTL
ExecStart=/bin/bash $PROJECT_DIR/deploy/update_pi.sh
TimeoutStartSec=20min
Nice=10
EOF
}

render_timer() {
  cat <<EOF
[Unit]
Description=Vérifie toutes les $INTERVAL minutes s'il y a une nouvelle version du site $SERVICE_NAME

[Timer]
OnBootSec=3min
OnUnitActiveSec=${INTERVAL}min
AccuracySec=30s

[Install]
WantedBy=timers.target
EOF
}

# Seule autorisation donnée : redémarrer le service du site, sans mot de passe.
render_sudoers() {
  cat <<EOF
# Généré par deploy/install_autoupdate.sh : permet à la mise à jour automatique
# de redémarrer le site (et rien d'autre).
$USER ALL=(root) NOPASSWD: $SYSTEMCTL restart $SERVICE_NAME
EOF
}

write_root_file() { # write_root_file chemin mode  (contenu sur stdin)
  local path="$1" mode="${2:-644}"
  $SUDO mkdir -p "$(dirname "$path")"
  $SUDO tee "$path" >/dev/null
  $SUDO chmod "$mode" "$path"
}

do_uninstall() {
  info "Arrêt et suppression du timer $UNIT…"
  $SUDO "$SYSTEMCTL" disable --now "$UNIT.timer" 2>/dev/null || true
  $SUDO rm -f "$SYSTEMD_DIR/$UNIT.timer" "$SYSTEMD_DIR/$UNIT.service" "$SUDOERS_DIR/$UNIT"
  $SUDO "$SYSTEMCTL" daemon-reload
  echo "Mise à jour automatique désactivée (les mises à jour manuelles restent possibles)."
}

do_install() {
  [[ -d "$PROJECT_DIR/.git" ]] || die "Dépôt introuvable : $PROJECT_DIR (variable APP_DIR ?)"
  [[ -f "$PROJECT_DIR/deploy/update_pi.sh" ]] \
    || die "deploy/update_pi.sh absent : faites d'abord « git pull origin main » dans $PROJECT_DIR."
  $SUDO test -f "$ENV_FILE" || die "$ENV_FILE introuvable : le site est-il installé (deploy/setup_pi.sh) ?"
  "$SYSTEMCTL" cat "$SERVICE_NAME.service" >/dev/null 2>&1 \
    || die "Service $SERVICE_NAME.service introuvable : installez d'abord le site (deploy/setup_pi.sh)."

  TMP_SUDOERS="$(mktemp)"; trap 'rm -f "$TMP_SUDOERS"' EXIT
  render_sudoers >"$TMP_SUDOERS"
  chmod 440 "$TMP_SUDOERS"
  if command -v visudo >/dev/null; then
    $SUDO visudo -cf "$TMP_SUDOERS" >/dev/null || die "Règle sudo générée invalide (visudo) : abandon, rien n'a été modifié."
  else
    echo "  ⚠ visudo introuvable : règle sudo non validée." >&2
  fi

  info "Installation de $UNIT.service et $UNIT.timer (toutes les $INTERVAL min)…"
  render_service | write_root_file "$SYSTEMD_DIR/$UNIT.service" 644
  render_timer   | write_root_file "$SYSTEMD_DIR/$UNIT.timer" 644
  write_root_file "$SUDOERS_DIR/$UNIT" 440 <"$TMP_SUDOERS"
  $SUDO "$SYSTEMCTL" daemon-reload
  $SUDO "$SYSTEMCTL" enable --now "$UNIT.timer"

  echo
  echo "Mise à jour automatique activée."
  "$SYSTEMCTL" list-timers "$UNIT.timer" --no-pager 2>/dev/null || true
  cat <<EOF

  Commandes utiles :
    sudo systemctl start $UNIT           lancer une vérification maintenant
    journalctl -u $UNIT -n 50 --no-pager  voir ce qui s'est passé
    cat $APP_DIR/last_deploy.txt          résultat du dernier déploiement
    bash $PROJECT_DIR/deploy/update_pi.sh --check   y a-t-il une mise à jour en attente ?
    sudo systemctl disable --now $UNIT.timer        suspendre (ex. pendant une manip manuelle)
    bash deploy/install_autoupdate.sh --uninstall   tout retirer
EOF
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --interval) INTERVAL="${2:?--interval demande un nombre de minutes}"; shift ;;
      --dry-run) DRY_RUN=1 ;;
      --uninstall) UNINSTALL=1 ;;
      -h|--help) sed -n '2,/^# =====*$/p' "$0" | sed 's/^# \{0,1\}//' | head -n 16; exit 0 ;;
      *) echo "Option inconnue : $1" >&2; exit 2 ;;
    esac
    shift
  done
  [[ "$INTERVAL" =~ ^[0-9]+$ && "$INTERVAL" -ge 1 && "$INTERVAL" -le 1440 ]] \
    || die "--interval attend un nombre de minutes entre 1 et 1440."

  if [[ $DRY_RUN -eq 1 ]]; then
    printf '== %s/%s.service ==\n' "$SYSTEMD_DIR" "$UNIT"; render_service
    printf '\n== %s/%s.timer ==\n' "$SYSTEMD_DIR" "$UNIT"; render_timer
    printf '\n== %s/%s ==\n' "$SUDOERS_DIR" "$UNIT"; render_sudoers
    exit 0
  fi

  [[ $EUID -ne 0 ]] || die "Ne lancez pas ce script avec sudo ni en root : il demande les droits quand il en a besoin."
  [[ -z "$SUDO" ]] || sudo -v || die "sudo n'est pas utilisable pour cet utilisateur."

  if [[ $UNINSTALL -eq 1 ]]; then do_uninstall; else do_install; fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
