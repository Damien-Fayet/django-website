#!/usr/bin/env bash
# =============================================================================
# setup_pi.sh — installation du site « avent » sur Raspberry Pi 1 / Pi 3
#
# Auto-porteur : ne dépend que de bash, curl et git. Étape par étape, avec suivi
# de l'avancement, relançable (les étapes déjà faites sont mémorisées).
#
# Usage :  bash setup_pi.sh [options]
#   --domain avent.exemple.com   domaine public du site (sinon demandé)
#   --db /chemin/db.sqlite3      base de données existante à reprendre
#   --yes                        ne pose aucune question (valeurs par défaut)
#   --skip-tunnel                n'installe pas Cloudflare Tunnel
#   --http2                      force HTTP/2 pour le tunnel (réseaux filtrant QUIC)
#   --profile pi1|pi3            force le profil matériel (sinon détection auto)
#   --from N / --only N          reprend à partir de l'étape N / ne lance que N
#   --dry-run                    affiche les étapes sans rien exécuter
#   --reset                      oublie les étapes déjà réalisées
#   --help                       cette aide
#
# Variables d'environnement utiles : CLOUDFLARE_TUNNEL_TOKEN (jeton du tunnel,
# évite la saisie), APP_DIR (défaut /srv/siteAvent), REPO_URL.
# Ne lancez PAS ce script avec sudo : il l'appelle lui-même quand il le faut.
# =============================================================================
set -Eeuo pipefail

# ---------- Configuration (surchargeable par l'environnement) -----------------
APP_DIR="${APP_DIR:-/srv/siteAvent}"
REPO_URL="${REPO_URL:-https://github.com/Damien-Fayet/django-website.git}"
SERVICE_NAME="${SERVICE_NAME:-avent}"
ENV_FILE="${ENV_FILE:-/etc/avent.env}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
STATE_FILE="${STATE_FILE:-$HOME/.setup_pi.state}"
LOG_FILE="${LOG_FILE:-$HOME/setup_pi.log}"
SUDO="${SUDO-sudo}"   # SUDO="" pour les tests sans droits root

USER="${USER:-$(id -un)}"   # certains shells (cron, conteneurs) ne le définissent pas
PROJECT_DIR="$APP_DIR/django-website"
VENV_DIR="$APP_DIR/venv"

# ---------- Options -----------------------------------------------------------
YES=0; DRY_RUN=0; SKIP_TUNNEL=0; HTTP2=""; DOMAIN=""; DB_SOURCE=""
FROM_STEP=0; ONLY_STEP=0; RESET=0; PROFILE="${PI_PROFILE:-}"

# ---------- Affichage ---------------------------------------------------------
if [[ -t 1 ]]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[36m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""; C_OFF=""
fi

# Masque tout jeton Cloudflare (chaîne base64 commençant par eyJ) avant écriture dans le journal.
mask() { sed -E 's/eyJ[A-Za-z0-9_=+\/-]{20,}/***MASQUÉ***/g'; }

log()  { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | mask >>"$LOG_FILE"; }
info() { printf '    %s\n' "$*"; log "$*"; }
warn() { printf '    %s⚠ %s%s\n' "$C_YELLOW" "$*" "$C_OFF"; log "AVERTISSEMENT: $*"; }
die()  {
  printf '\n%s✘ %s%s\n' "$C_RED" "$*" "$C_OFF" >&2
  log "ERREUR: $*"
  if [[ -s "$LOG_FILE" ]]; then
    printf '  Dernières lignes du journal (%s) :\n' "$LOG_FILE" >&2
    tail -n 12 "$LOG_FILE" | sed 's/^/    | /' >&2
  fi
  [[ "${CURRENT_N:-0}" -gt 0 ]] && printf '  Corrigez le problème puis relancez : bash %s --from %s\n' "$0" "$CURRENT_N" >&2
  exit 1
}

# Pose une question (oui/non) ; avec --yes, renvoie la valeur par défaut.
confirm() { # confirm "question" [o|n]
  local q="$1" def="${2:-o}" ans
  if [[ $YES -eq 1 || ! -t 0 ]]; then [[ "$def" == "o" ]]; return; fi
  read -r -p "    $q [$([[ $def == o ]] && echo 'O/n' || echo 'o/N')] " ans || true
  ans="${ans:-$def}"
  [[ "$ans" =~ ^[oOyY] ]]
}

# Exécute une commande, sortie (masquée) vers le journal ; échec = arrêt avec message.
run() {
  log "\$ $*"
  local rc=0
  "$@" 2>&1 | mask >>"$LOG_FILE" || rc=${PIPESTATUS[0]}
  if [[ $rc -ne 0 ]]; then die "La commande a échoué (code $rc) : $*"; fi
}

# Variante tolérante : l'échec est seulement journalisé.
run_ok() {
  log "\$ $*"
  local rc=0
  "$@" 2>&1 | mask >>"$LOG_FILE" || rc=${PIPESTATUS[0]}
  [[ $rc -eq 0 ]] || log "(code $rc ignoré)"
  return 0
}

write_root_file() { # write_root_file chemin mode  (contenu sur stdin)
  local path="$1" mode="${2:-644}"
  $SUDO mkdir -p "$(dirname "$path")"
  $SUDO tee "$path" >/dev/null
  $SUDO chmod "$mode" "$path"
}

# ---------- Fonctions pures (testables) ---------------------------------------

# Profil matériel : pi1 (ARMv6, 512 Mo) ou pi3 (ARMv7/ARMv8, ≥ 1 Go).
detect_profile() {
  [[ -n "$PROFILE" ]] && { echo "$PROFILE"; return; }
  local model_file="${PI_MODEL_FILE:-/proc/device-tree/model}" model="" arch="${PI_ARCH:-$(uname -m)}"
  [[ -r "$model_file" ]] && model="$(tr -d '\0' <"$model_file")"
  if [[ "$arch" == "armv6l" || "$model" =~ ^Raspberry\ Pi\ (Model|Zero) ]]; then
    echo pi1
  else
    echo pi3
  fi
}

set_profile_vars() { # définit les réglages selon le profil
  case "$1" in
    pi1)
      GUNICORN_ARGS="--workers 1 --threads 2 --timeout 120"
      VENV_FLAGS="--system-site-packages"
      NEED_SWAP=1; WAIT_HTTP=180; DEFAULT_HTTP2=1 ;;
    *)
      GUNICORN_ARGS="--workers 2 --timeout 60"
      VENV_FLAGS=""
      NEED_SWAP=0; WAIT_HTTP=60; DEFAULT_HTTP2=0 ;;
  esac
}

# "deb:URL" ou "bin:URL" selon l'architecture (chemin vers les publications officielles).
cloudflared_source() {
  local arch="${PI_ARCH:-$(uname -m)}" base="https://github.com/cloudflare/cloudflared/releases/latest/download"
  case "$arch" in
    aarch64|arm64) echo "deb:$base/cloudflared-linux-arm64.deb" ;;
    armv7l|armv8l) echo "deb:$base/cloudflared-linux-armhf.deb" ;;
    armv6l)        echo "bin:$base/cloudflared-linux-arm" ;;
    x86_64)        echo "deb:$base/cloudflared-linux-amd64.deb" ;;
    *) return 1 ;;
  esac
}

valid_domain() { [[ "$1" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$ ]]; }

# Clé secrète : caractères URL-safe uniquement (aucun $, #, !, % à protéger).
gen_secret() { python3 -c 'import secrets; print(secrets.token_urlsafe(50))'; }

PROD_MARKER="# --- Production (Pi derrière Cloudflare Tunnel) ---"

# Ajoute UNE SEULE FOIS le bloc de production à la fin de settings.py.
append_prod_block() { # append_prod_block fichier domaine
  local file="$1" domain="$2"
  if grep -qF "$PROD_MARKER" "$file"; then return 1; fi
  cp -p "$file" "$file.bak"
  cat >>"$file" <<EOF

$PROD_MARKER
DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = ["$domain"]
CSRF_TRUSTED_ORIGINS = ["https://$domain"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
EOF
}

render_service() {
  cat <<EOF
[Unit]
Description=Site avent (gunicorn)
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/gunicorn mysite.wsgi --bind 127.0.0.1:8000 $GUNICORN_ARGS
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

render_backup_script() {
  cat <<EOF
#!/bin/bash
# Sauvegarde quotidienne de la base SQLite (copie cohérente), rotation sur 7 jours.
set -euo pipefail
DEST="$APP_DIR/backups"
mkdir -p "\$DEST"
sqlite3 "$PROJECT_DIR/db.sqlite3" ".backup \$DEST/db-\$(date +%F).sqlite3"
find "\$DEST" -name 'db-*.sqlite3' -mtime +7 -delete
EOF
}

# ---------- État (reprise) ----------------------------------------------------
is_done()   { [[ -f "$STATE_FILE" ]] && grep -qx "$1" "$STATE_FILE"; }
mark_done() { is_done "$1" || echo "$1" >>"$STATE_FILE"; }
forget()    { [[ -f "$STATE_FILE" ]] && sed -i "/^$1\$/d" "$STATE_FILE" || true; }

manage() { # exécute manage.py avec l'environnement de production
  ( set -a; source <($SUDO cat "$ENV_FILE"); set +a
    cd "$PROJECT_DIR"; "$VENV_DIR/bin/python" manage.py "$@" )
}

# ---------- Étapes ------------------------------------------------------------
# Format : "id|titre|description (utilisée par --dry-run)"
STEPS=(
  "preflight|Pré-contrôles|Vérifie utilisateur, sudo, Internet, espace disque, Python ≥ 3.10, heure"
  "apt|Paquets système|apt : python3-venv, pip, git, sqlite3, curl (+ python3-pil sur Pi 1), fuseau Europe/Paris"
  "swap|Mémoire d'échange|Pi 1 uniquement : swap de 512 Mo"
  "clone|Code du site|git clone --depth 1 dans $APP_DIR"
  "venv|Environnement Python|venv + Django 5.1, ckeditor-5, requests, pillow, gunicorn, whitenoise"
  "config|Configuration de production|Bloc de prod dans settings.py + clé secrète dans $ENV_FILE"
  "db|Base de données|Copie optionnelle de la base, migrate, collectstatic, compte admin"
  "service|Service du site|Unité systemd '$SERVICE_NAME' (gunicorn) + test local"
  "tunnel|Cloudflare Tunnel|Installation de cloudflared, jeton, délai de démarrage allongé"
  "backup|Sauvegardes|Script de sauvegarde SQLite + cron quotidien (4 h)"
  "journald|Usure de la carte SD|Journaux systemd en mémoire (Storage=volatile)"
)

step_preflight() {
  [[ $EUID -ne 0 ]] || die "Ne lancez pas ce script avec sudo ni en root : il demande les droits quand il en a besoin."
  if [[ -n "$SUDO" ]]; then
    info "Droits administrateur nécessaires : saisissez votre mot de passe si demandé."
    sudo -v || die "sudo n'est pas utilisable pour cet utilisateur."
    # Garde la session sudo ouverte pendant les longues installations.
    ( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null; sleep 50; done ) &
  fi
  command -v apt-get >/dev/null || die "apt-get introuvable : ce script vise Raspberry Pi OS / Debian."
  curl -fsS --max-time 15 -o /dev/null https://github.com || die "Pas d'accès à Internet (github.com injoignable)."
  local parent; parent="$(dirname "$APP_DIR")"; mkdir -p "$parent" 2>/dev/null || true
  local free_mb; free_mb=$(df -Pm "$parent" 2>/dev/null | awk 'NR==2{print $4}')
  [[ -z "${free_mb:-}" || "$free_mb" -ge 500 ]] || die "Espace disque insuffisant (${free_mb} Mo libres, 500 Mo requis)."
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
    || die "Python 3.10 minimum requis (Raspberry Pi OS Bookworm ou plus récent)."
  info "Profil détecté : $PROFILE ($(uname -m)), Python $(python3 -c 'import platform;print(platform.python_version())')"
  local ntp; ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo unknown)"
  [[ "$ntp" == "yes" ]] || warn "Horloge non synchronisée (NTP : $ntp). Le déblocage des jours dépend de l'heure."
}

step_apt() {
  local pkgs=(python3-venv python3-pip git sqlite3 curl)
  [[ "$PROFILE" == "pi1" ]] && pkgs+=(python3-pil)
  run $SUDO apt-get update
  run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
  run_ok $SUDO timedatectl set-timezone Europe/Paris
  run_ok $SUDO timedatectl set-ntp true
}

step_swap() {
  if [[ "${NEED_SWAP:-0}" -ne 1 ]]; then info "Inutile sur ce profil."; return; fi
  local swap_mb; swap_mb=$(free -m | awk '/^Swap:/{print $2}')
  if [[ "${swap_mb:-0}" -ge 400 ]]; then info "Swap déjà suffisant (${swap_mb} Mo)."; return; fi
  if ! command -v dphys-swapfile >/dev/null; then warn "dphys-swapfile absent : swap non configuré."; return; fi
  run $SUDO sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
  run $SUDO dphys-swapfile setup
  run $SUDO dphys-swapfile swapon
}

step_clone() {
  $SUDO mkdir -p "$APP_DIR"
  $SUDO chown "$USER:" "$APP_DIR"
  if [[ -d "$PROJECT_DIR/.git" ]]; then
    info "Dépôt déjà présent dans $PROJECT_DIR (conservé tel quel)."
    return
  fi
  run git clone --depth 1 "$REPO_URL" "$PROJECT_DIR"
}

step_venv() {
  [[ -d "$PROJECT_DIR" ]] || die "Code absent : lancez d'abord l'étape clone."
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    # shellcheck disable=SC2086
    run python3 -m venv $VENV_FLAGS "$VENV_DIR"
  fi
  export PIP_DISABLE_PIP_VERSION_CHECK=1
  local req="$PROJECT_DIR/requirements.txt"
  if [[ "$PROFILE" == "pi1" ]]; then
    # Pillow vient du paquet apt (évite une compilation très longue sur ARMv6).
    local filtered; filtered="$(mktemp)"
    grep -vi '^pillow' "$req" >"$filtered"
    run "$VENV_DIR/bin/pip" install --prefer-binary --progress-bar off -r "$filtered" gunicorn whitenoise
    rm -f "$filtered"
  else
    run "$VENV_DIR/bin/pip" install --prefer-binary --progress-bar off -r "$req" gunicorn whitenoise
  fi
  run "$VENV_DIR/bin/python" -c "import django; print(django.get_version())"
}

step_config() {
  local settings="$PROJECT_DIR/mysite/settings.py"
  [[ -f "$settings" ]] || die "settings.py introuvable : $settings"
  # Domaine
  if [[ -z "$DOMAIN" ]]; then
    if [[ $YES -eq 1 || ! -t 0 ]]; then die "Domaine manquant : utilisez --domain."; fi
    read -r -p "    Domaine public du site (ex. avent.exemple.com) : " DOMAIN
  fi
  DOMAIN="$(echo "$DOMAIN" | tr '[:upper:]' '[:lower:]')"
  valid_domain "$DOMAIN" || die "Domaine invalide : '$DOMAIN'"
  info "Domaine : $DOMAIN"
  # Bloc de production (une seule fois, tout à la fin du fichier)
  if append_prod_block "$settings" "$DOMAIN"; then
    info "Bloc de production ajouté à la fin de settings.py (copie : settings.py.bak)."
  else
    info "Bloc de production déjà présent (rien à faire)."
    grep -qF "\"$DOMAIN\"" "$settings" || warn "Le domaine du bloc existant diffère de $DOMAIN : vérifiez ALLOWED_HOSTS."
  fi
  run_ok git -C "$PROJECT_DIR" update-index --skip-worktree mysite/settings.py
  # Clé secrète, écrite directement dans le fichier sans jamais s'afficher.
  if $SUDO test -f "$ENV_FILE" && $SUDO grep -q '^DJANGO_SECRET_KEY=' "$ENV_FILE"; then
    info "Clé secrète déjà présente dans $ENV_FILE (conservée)."
  else
    printf 'DJANGO_SECRET_KEY=%s\n' "$(gen_secret)" | write_root_file "$ENV_FILE" 600
    info "Clé secrète générée dans $ENV_FILE (lecture réservée à root)."
  fi
  echo "$DOMAIN" >"$APP_DIR/.domain"
}

step_db() {
  local db="$PROJECT_DIR/db.sqlite3"
  if [[ -n "$DB_SOURCE" ]]; then
    [[ -f "$DB_SOURCE" ]] || die "Base introuvable : $DB_SOURCE"
    [[ -f "$db" ]] && cp -p "$db" "$db.bak.$(date +%s)"
    run cp "$DB_SOURCE" "$db"
    info "Base reprise depuis $DB_SOURCE."
  elif [[ -f "$db" ]]; then
    info "Base existante conservée."
  else
    info "Nouvelle base vide (aucune --db fournie)."
  fi
  info "Migrations (peut durer 1 à 2 minutes sur un Pi 1)…"
  run_manage migrate --noinput
  run_manage collectstatic --noinput
  local has_admin
  has_admin="$(manage shell -c 'from django.contrib.auth import get_user_model as g; print(g().objects.filter(is_superuser=True).exists())' 2>>"$LOG_FILE" | tail -n1)"
  if [[ "$has_admin" != "True" ]]; then
    if [[ $YES -eq 0 && -t 0 ]] && confirm "Aucun compte administrateur. En créer un maintenant ?" o; then
      manage createsuperuser || warn "Création du compte admin abandonnée."
    else
      warn "Aucun administrateur : lancez plus tard « python manage.py createsuperuser »."
    fi
  else
    info "Un compte administrateur existe déjà."
  fi
}

run_manage() { # manage.py avec sortie vers le journal
  log "\$ manage.py $*"
  local rc=0
  manage "$@" 2>&1 | mask >>"$LOG_FILE" || rc=${PIPESTATUS[0]}
  [[ $rc -eq 0 ]] || die "manage.py $* a échoué (code $rc)."
}

wait_for_site() { # wait_for_site domaine délai
  local domain="$1" limit="$2" waited=0 code=""
  while [[ $waited -lt $limit ]]; do
    code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H "Host: $domain" http://127.0.0.1:8000/accounts/login/ || true)"
    [[ "$code" == "200" ]] && return 0
    sleep 3; waited=$((waited + 3))
    printf '\r    attente du site… %ss (HTTP %s)   ' "$waited" "${code:-—}"
  done
  printf '\n'
  return 1
}

step_service() {
  local domain; domain="${DOMAIN:-$(cat "$APP_DIR/.domain" 2>/dev/null || true)}"
  [[ -n "$domain" ]] || die "Domaine inconnu : relancez l'étape config (--only 6)."
  render_service | write_root_file "$SYSTEMD_DIR/$SERVICE_NAME.service" 644
  run $SUDO systemctl daemon-reload
  run $SUDO systemctl enable "$SERVICE_NAME"
  run $SUDO systemctl restart "$SERVICE_NAME"
  if wait_for_site "$domain" "$WAIT_HTTP"; then
    printf '\n'; info "Le site répond (HTTP 200) en local."
  else
    $SUDO journalctl -u "$SERVICE_NAME" -n 20 --no-pager 2>&1 | mask >>"$LOG_FILE" || true
    die "Le site ne répond pas sur 127.0.0.1:8000 : voir « journalctl -u $SERVICE_NAME -n 50 »."
  fi
}

step_tunnel() {
  if [[ $SKIP_TUNNEL -eq 1 ]]; then info "Ignoré (--skip-tunnel)."; return; fi
  if $SUDO systemctl is-active --quiet cloudflared 2>/dev/null; then
    info "cloudflared est déjà actif (conservé)."; return
  fi
  local src kind url
  src="$(cloudflared_source)" || die "Architecture non prise en charge : $(uname -m)"
  kind="${src%%:*}"; url="${src#*:}"
  if ! command -v cloudflared >/dev/null; then
    local tmp; tmp="$(mktemp)"
    info "Téléchargement de cloudflared ($kind)…"
    run curl -fsSL --retry 3 -o "$tmp" "$url"
    if [[ "$kind" == "deb" ]]; then run $SUDO dpkg -i "$tmp"; else run $SUDO install -m 755 "$tmp" /usr/local/bin/cloudflared; fi
    rm -f "$tmp"
  fi
  run cloudflared --version
  if [[ -f "$SYSTEMD_DIR/cloudflared.service" ]]; then
    warn "Un service cloudflared existe mais n'est pas actif : il sera réinstallé avec le nouveau jeton."
    run_ok $SUDO cloudflared service uninstall
  fi
  # Jeton : variable d'environnement, sinon saisie masquée. Jamais écrit dans le journal.
  local token="${CLOUDFLARE_TUNNEL_TOKEN:-}"
  if [[ -z "$token" ]]; then
    if [[ $YES -eq 1 || ! -t 0 ]]; then warn "Pas de jeton : tunnel non configuré (CLOUDFLARE_TUNNEL_TOKEN)."; return; fi
    info "Collez le jeton du tunnel (Cloudflare Zero Trust → Tunnels), puis Entrée (rien ne s'affiche) ; Entrée seul pour ignorer."
    read -rs -p "    Jeton : " token; printf '\n'
  fi
  [[ -n "$token" ]] || { warn "Tunnel ignoré (pas de jeton)."; return; }
  [[ "$token" =~ ^eyJ[A-Za-z0-9_=+/.-]{40,}$ ]] || die "Ce jeton n'a pas le bon format (il commence par « eyJ » et est long)."
  # Le jeton passe en argument de la commande officielle ; sa sortie est masquée dans le journal.
  $SUDO cloudflared service install "$token" 2>&1 | mask >>"$LOG_FILE" \
    || die "cloudflared service install a échoué (jeton refusé ou service déjà installé)."
  unset token
  local unit="$SYSTEMD_DIR/cloudflared.service"
  $SUDO chmod 600 "$unit"   # le jeton y figure : réservé à root
  # Démarrage lent sur Pi : la valeur par défaut (15 s) fait échouer le service.
  printf '[Service]\nTimeoutStartSec=180\n' | write_root_file "$SYSTEMD_DIR/cloudflared.service.d/override.conf" 644
  local use_http2="$HTTP2"; [[ -n "$use_http2" ]] || use_http2="${DEFAULT_HTTP2:-0}"
  if [[ "$use_http2" == "1" ]] && ! $SUDO grep -q -- '--protocol http2' "$unit"; then
    run $SUDO sed -i 's# tunnel run# tunnel --protocol http2 run#' "$unit"
    info "Protocole HTTP/2 activé (plus léger que QUIC)."
  fi
  run $SUDO systemctl daemon-reload
  run $SUDO systemctl enable cloudflared
  info "Démarrage du tunnel (jusqu'à 3 minutes sur un Pi lent)…"
  run $SUDO timeout 200 systemctl restart cloudflared
  $SUDO systemctl is-active --quiet cloudflared || die "cloudflared n'est pas actif : « journalctl -u cloudflared -n 50 »."
  info "Tunnel actif."
}

step_backup() {
  local script="$APP_DIR/backup.sh"
  render_backup_script >"$script"
  chmod +x "$script"
  local current; current="$(crontab -l 2>/dev/null || true)"
  { printf '%s\n' "$current" | grep -vF "$script" || true; echo "0 4 * * * $script"; } | crontab -
  info "Sauvegarde quotidienne à 4 h dans $APP_DIR/backups (7 jours conservés)."
  info "Pensez à copier ce dossier hors du Pi (ordinateur, clé USB, rclone)."
}

step_journald() {
  printf '[Journal]\nStorage=volatile\n' | write_root_file /etc/systemd/journald.conf.d/volatile.conf 644
  run_ok $SUDO systemctl restart systemd-journald
}

report() {
  local domain; domain="${DOMAIN:-$(cat "$APP_DIR/.domain" 2>/dev/null || echo 'votre-domaine')}"
  printf '\n%s== Terminé ==%s\n' "$C_BOLD" "$C_OFF"
  for svc in "$SERVICE_NAME" cloudflared; do
    printf '  %-12s %s\n' "$svc" "$($SUDO systemctl is-active "$svc" 2>/dev/null || echo 'non installé')"
  done
  cat <<EOF

  À faire dans Cloudflare si ce n'est pas déjà fait :
    Zero Trust → Networks → Tunnels → votre tunnel → Public Hostname :
    sous-domaine/domaine = $domain, service HTTP, URL localhost:8000
  Puis ouvrir : https://$domain

  Commandes utiles :
    journalctl -u $SERVICE_NAME -f          (journal du site en direct)
    journalctl -u cloudflared -f            (journal du tunnel)
    sudo systemctl restart $SERVICE_NAME    (redémarrer le site)
  Mise à jour du site : voir DEPLOY_PI.md (section « Mettre à jour le site »).
  Journal de ce script : $LOG_FILE
EOF
}

# ---------- Moteur : progression, reprise ------------------------------------
progress_bar() { # progress_bar fait total
  local done_n=$1 total=$2 width=24 filled i bar=""
  filled=$(( done_n * width / total ))
  for ((i = 0; i < width; i++)); do if (( i < filled )); then bar+="█"; else bar+="░"; fi; done
  printf '%s %3d%%' "$bar" $(( done_n * 100 / total ))
}

CURRENT_STEP=""; CURRENT_N=0
on_error() { # appelé par le trap ERR
  local rc=$? line=$1
  trap - ERR
  printf '\n%s✘ Échec à l'"'"'étape « %s » (ligne %s, code %s).%s\n' "$C_RED" "${CURRENT_STEP:-?}" "$line" "$rc" "$C_OFF" >&2
  log "ERREUR étape '${CURRENT_STEP:-?}' ligne $line code $rc"
  tail -n 12 "$LOG_FILE" | sed 's/^/    | /' >&2
  printf '  Corrigez le problème puis relancez : bash %s --from %s\n' "$0" "${CURRENT_N:-1}" >&2
  exit "$rc"
}

run_steps() {
  local total=${#STEPS[@]} n=0 entry id title desc fn started status
  for entry in "${STEPS[@]}"; do
    n=$((n + 1)); CURRENT_N=$n
    IFS='|' read -r id title desc <<<"$entry"
    fn="step_$id"
    CURRENT_STEP="$title"

    if [[ $ONLY_STEP -ne 0 && $n -ne $ONLY_STEP ]]; then continue; fi
    printf '%s[%2d/%d]%s %s %s%s%s\n' "$C_BLUE" "$n" "$total" "$C_OFF" "$(progress_bar $((n - 1)) "$total")" "$C_BOLD" "$title" "$C_OFF"

    if [[ $DRY_RUN -eq 1 ]]; then printf '        (simulation) %s\n' "$desc"; continue; fi
    # Les pré-contrôles tournent toujours (ils ouvrent la session sudo) ; les autres sont mémorisés.
    if [[ $ONLY_STEP -eq 0 && "$id" != "preflight" ]] && is_done "$id"; then
      printf '        %s↷ déjà fait%s\n' "$C_YELLOW" "$C_OFF"; continue
    fi
    log "=== Étape $n/$total : $title ==="
    started=$SECONDS
    "$fn"
    [[ "$id" == "preflight" ]] || mark_done "$id"
    status="$(( SECONDS - started ))"
    printf '        %s✔ terminé%s (%ss)\n' "$C_GREEN" "$C_OFF" "$status"
  done
  [[ $DRY_RUN -eq 1 ]] || printf '%s[%d/%d]%s %s\n' "$C_BLUE" "$total" "$total" "$C_OFF" "$(progress_bar "$total" "$total")"
}

usage() { sed -n '2,/^# =====*$/p' "$0" | sed 's/^# \{0,1\}//' | head -n 28; }

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes|-y) YES=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --skip-tunnel) SKIP_TUNNEL=1 ;;
      --http2) HTTP2=1 ;;
      --reset) RESET=1 ;;
      --domain) DOMAIN="${2:?--domain demande une valeur}"; shift ;;
      --db) DB_SOURCE="${2:?--db demande un chemin}"; shift ;;
      --profile) PROFILE="${2:?--profile demande pi1 ou pi3}"; shift ;;
      --from) FROM_STEP="${2:?--from demande un numéro}"; shift ;;
      --only) ONLY_STEP="${2:?--only demande un numéro}"; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Option inconnue : $1" >&2; usage; exit 2 ;;
    esac
    shift
  done
  [[ "$PROFILE" =~ ^(pi1|pi3|)$ ]] || { echo "--profile doit valoir pi1 ou pi3" >&2; exit 2; }
  [[ "$FROM_STEP" =~ ^[0-9]+$ && "$ONLY_STEP" =~ ^[0-9]+$ ]] || { echo "--from/--only attendent un nombre" >&2; exit 2; }

  umask 022
  : >>"$LOG_FILE"; chmod 600 "$LOG_FILE" 2>/dev/null || true
  [[ $RESET -eq 1 ]] && rm -f "$STATE_FILE"
  trap 'on_error $LINENO' ERR

  PROFILE="$(detect_profile)"
  set_profile_vars "$PROFILE"
  # --from N : les étapes à partir de N sont refaites
  if [[ $FROM_STEP -gt 0 ]]; then
    local i=0 entry id
    for entry in "${STEPS[@]}"; do i=$((i + 1)); id="${entry%%|*}"; (( i >= FROM_STEP )) && forget "$id"; done
  fi

  printf '%sInstallation du site avent — profil %s%s  (journal : %s)\n\n' "$C_BOLD" "$PROFILE" "$C_OFF" "$LOG_FILE"
  log "Démarrage : profil=$PROFILE dry_run=$DRY_RUN from=$FROM_STEP only=$ONLY_STEP"
  run_steps
  if [[ $DRY_RUN -eq 0 ]]; then report; else printf '\nSimulation terminée : rien n'"'"'a été modifié.\n'; fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
