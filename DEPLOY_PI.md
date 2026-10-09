# Déploiement sur Raspberry Pi (Pi 1 ou Pi 3) avec Cloudflare Tunnel

Procédure pour héberger le site Django (avent2026) sur un Raspberry Pi, derrière un **Cloudflare Tunnel**
(aucun port à ouvrir, HTTPS géré par Cloudflare). Les étapes sont communes aux deux modèles ;
les différences sont signalées **[Pi 1]** et **[Pi 3]**.

## Valeurs à adapter

| Élément | Exemple utilisé ici |
|---|---|
| Utilisateur Linux du Pi | `TON_USER` |
| Nom d'hôte du Pi | `NOM_HOTE` |
| Dossier d'installation | `/srv/siteAvent` |
| Domaine du site | `avent.damienfayet.com` |

## Pi 1 ou Pi 3 : à quoi s'attendre

| | Pi 1 | Pi 3 |
|---|---|---|
| Processeur / RAM | 1 cœur ARMv6, 512 Mo | 4 cœurs ARMv8, 1 Go |
| OS à choisir | Raspberry Pi OS Lite **32 bits** | Raspberry Pi OS Lite **64 bits** |
| Réseau | Ethernet (pas de Wi-Fi intégré) | Ethernet conseillé, Wi-Fi possible |
| Gunicorn | 1 worker, 2 threads | 2 workers |
| Démarrage de l'appli | lent (plusieurs dizaines de secondes) | rapide |
| Stockage | carte SD uniquement | carte SD, ou SSD USB possible |

Le Pi 1 suffit pour ~30 personnes qui jouent quelques minutes par jour, mais les pages sont plus lentes et la
carte SD est le point faible. Si tu as le choix, prends le Pi 3.

---

## 1. Installer l'OS

Avec **Raspberry Pi Imager**, choisis « Raspberry Pi OS Lite » (32 bits pour le Pi 1, 64 bits pour le Pi 3).
Dans les réglages avancés : nom d'hôte, utilisateur, mot de passe, et **SSH activé**. Branche le câble réseau,
démarre, puis connecte-toi :

```bash
ssh TON_USER@NOM_HOTE.local
```

## 2. Mise à jour et paquets de base

```bash
sudo apt update && sudo apt full-upgrade -y
sudo timedatectl set-timezone Europe/Paris
timedatectl          # "System clock synchronized: yes" doit s'afficher
sudo apt install -y python3-venv python3-pip git sqlite3
```

Le Pi n'a pas d'horloge interne : l'heure vient du réseau au démarrage. Le déblocage des jours en dépend,
donc vérifie que la synchronisation est active.

### [Pi 1 seulement] Swap et Pillow depuis les paquets

```bash
sudo apt install -y python3-pil
sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
sudo dphys-swapfile setup && sudo dphys-swapfile swapon
```

Pillow est la seule dépendance lourde à compiler. Le swap évite un plantage par manque de mémoire.

## 3. Récupérer le code et créer l'environnement Python

```bash
sudo mkdir -p /srv/siteAvent && sudo chown $USER: /srv/siteAvent
cd /srv/siteAvent
git clone --depth 1 https://github.com/Damien-Fayet/django-website.git
```

Environnement virtuel :

- **[Pi 3]** : `python3 -m venv venv`
- **[Pi 1]** : `python3 -m venv --system-site-packages venv` (réutilise le Pillow installé par apt)

```bash
source venv/bin/activate
pip install -r django-website/requirements.txt gunicorn whitenoise
```

Sur Raspberry Pi OS, `pip` utilise piwheels (paquets précompilés) : l'installation est rapide.
**[Pi 1]** : si tu vois « Building wheel for pillow » qui dure, fais `Ctrl+C` et lance plutôt :

```bash
pip install "Django>=5.1,<5.2" django-ckeditor-5 requests gunicorn whitenoise
```

(Pillow vient déjà des paquets apt.)

## 4. Configuration de production

Ajoute ce bloc **tout à la fin** de `/srv/siteAvent/django-website/mysite/settings.py`
(après la définition de `MIDDLEWARE`, sinon `NameError: name 'MIDDLEWARE' is not defined`).
Adapte le domaine :

```python
# --- Production (Pi derrière Cloudflare Tunnel) ---
DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = ["avent.damienfayet.com"]
CSRF_TRUSTED_ORIGINS = ["https://avent.damienfayet.com"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
```

Pour que `git pull` ne soit pas bloqué par cette modification locale (le fichier est suivi par git) :

```bash
cd /srv/siteAvent/django-website
git update-index --skip-worktree mysite/settings.py
```

### Clé secrète

Génère-la directement dans un fichier, sans l'afficher à l'écran :

```bash
echo "DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key as g; print(g())')" | sudo tee /etc/avent.env > /dev/null
sudo chmod 600 /etc/avent.env
```

Si la clé générée contient un `$` ou un `#`, relance la commande pour en obtenir une autre (systemd les interprète).

> En bash, un `!` dans une commande déclenche l'expansion d'historique (`event not found`). Ne tape jamais une
> clé dans le terminal sans guillemets simples : `export DJANGO_SECRET_KEY='...'`.

## 5. Base de données, migrations, fichiers statiques

Copie ta base depuis ta machine (sauvegarde de PythonAnywhere, par exemple) :

```bash
scp db.sqlite3 TON_USER@NOM_HOTE.local:/srv/siteAvent/django-website/db.sqlite3
```

Puis, sur le Pi :

```bash
cd /srv/siteAvent/django-website
source ../venv/bin/activate
set -a; source <(sudo cat /etc/avent.env); set +a
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser    # seulement si tu n'as pas copié de base
```

**[Pi 1]** : `migrate` peut prendre une à deux minutes, c'est normal.

> Les migrations qui suppriment les anciennes apps sont irréversibles. Garde une copie de ta base d'origine
> (`db.sqlite3`) en dehors du dossier du projet avant de lancer `migrate`.

## 6. Lancer gunicorn en service systemd

Crée `/etc/systemd/system/avent.service` (`sudo nano`). Pour le **Pi 3** :

```ini
[Unit]
Description=Site avent (gunicorn)
After=network.target

[Service]
User=TON_USER
WorkingDirectory=/srv/siteAvent/django-website
EnvironmentFile=/etc/avent.env
ExecStart=/srv/siteAvent/venv/bin/gunicorn mysite.wsgi --bind 127.0.0.1:8000 --workers 2 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```

**[Pi 1]** : remplace la ligne `ExecStart` par :

```ini
ExecStart=/srv/siteAvent/venv/bin/gunicorn mysite.wsgi --bind 127.0.0.1:8000 --workers 1 --threads 2 --timeout 120
```

Active et teste :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avent
sleep 20     # [Pi 1] laisse le temps de démarrer
curl -I http://127.0.0.1:8000/accounts/login/    # doit répondre 200
sudo systemctl status avent --no-pager
```

## 7. Cloudflare Tunnel

### Installer `cloudflared`

**[Pi 3, OS 64 bits]**

```bash
curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb
```

**[Pi 1, OS 32 bits]** — binaire ARM de base (le paquet `armhf` vise des processeurs plus récents) :

```bash
sudo curl -L -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm
sudo chmod +x /usr/local/bin/cloudflared
cloudflared --version     # si "Illegal instruction", ce binaire ne convient pas à ton Pi
```

### Créer le tunnel dans le tableau de bord Cloudflare

1. **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**, nom : `pi-avent`.
2. Copie la commande avec le jeton et lance-la sur le Pi : `sudo cloudflared service install eyJ...`
   (elle installe le tunnel comme un service qui redémarre tout seul).
3. Onglet **Public Hostname** : sous-domaine `avent`, domaine `damienfayet.com`, service **HTTP**, URL `localhost:8000`.

Cloudflare crée l'enregistrement DNS automatiquement. Le plan gratuit suffit ; Cloudflare peut demander un moyen
de paiement à la première activation de Zero Trust.

### Tester

Ouvre `https://avent.damienfayet.com`, puis teste l'inscription (vérifie le CSRF), la connexion et `/admin/`.

## 8. Sauvegardes (indispensables, surtout sur carte SD)

Crée `/srv/siteAvent/backup.sh` :

```bash
#!/bin/bash
mkdir -p /srv/siteAvent/backups
sqlite3 /srv/siteAvent/django-website/db.sqlite3 ".backup /srv/siteAvent/backups/db-$(date +%F).sqlite3"
find /srv/siteAvent/backups -name 'db-*.sqlite3' -mtime +7 -delete
```

```bash
chmod +x /srv/siteAvent/backup.sh
(crontab -l 2>/dev/null; echo "0 4 * * * /srv/siteAvent/backup.sh") | crontab -
```

Copie régulièrement le dossier `backups/` hors du Pi (ordinateur, clé USB, ou `rclone` vers un cloud).
Ne copie jamais directement `db.sqlite3` pendant que le site tourne : utilise la commande `.backup`.

## 9. Réduire l'usure de la carte SD

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
printf "[Journal]\nStorage=volatile\n" | sudo tee /etc/systemd/journald.conf.d/volatile.conf
```

Les journaux restent en mémoire. **[Pi 3]** : tu pourras plus tard démarrer depuis un petit SSD USB (plus fiable).
**[Pi 1]** : le démarrage USB n'est pas possible, seule la carte SD fonctionne.

## 10. Mettre à jour le site

```bash
cd /srv/siteAvent/django-website && source ../venv/bin/activate
git pull origin main
pip install -r requirements.txt
set -a; source <(sudo cat /etc/avent.env); set +a
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart avent
```

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| Erreur 502 sur le domaine | gunicorn ne répond pas | `sudo journalctl -u avent -n 50 --no-pager` |
| Erreur 403 à l'inscription / connexion | `CSRF_TRUSTED_ORIGINS` ne correspond pas au domaine | Vérifier `https://` + domaine exact |
| Erreur 400 « Invalid host » | domaine absent de `ALLOWED_HOSTS` | Corriger `settings.py`, redémarrer le service |
| Page sans style | `collectstatic` non lancé, ou WhiteNoise absent | Relancer `collectstatic`; le bloc de l'étape 4 doit être en fin de fichier |
| `NameError: name 'MIDDLEWARE' is not defined` | bloc de l'étape 4 collé trop haut dans `settings.py` | Le déplacer à la toute fin |
| `-bash: ... event not found` | `!` dans une commande sans guillemets simples | Entourer la valeur de `'...'` |
| Un jour reste verrouillé alors qu'il est l'heure | heure du Pi incorrecte | `timedatectl` (NTP actif ?) |
| Images d'énigmes en 404 | avec `DEBUG=False`, Django ne sert plus `media/` | À prévoir quand tu ajouteras des images (service de `media/` à configurer) |
| `Illegal instruction` en lançant `cloudflared` [Pi 1] | binaire non adapté à ARMv6 | Demander une autre méthode |

## Limites à connaître

- Si le courant, la box ou le Pi tombe, le site est inaccessible. En décembre, prévois au minimum un
  redémarrage automatique (déjà couvert par `Restart=always` et le service `cloudflared`), idéalement un onduleur.
- Les statiques sont servies par WhiteNoise, mais pas `media/` (voir le tableau de dépannage).
