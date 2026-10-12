# Instructions projet — django-website

Monorepo Django (5.1) de sites perso pour la famille (~30 utilisateurs). Hébergé sur **PythonAnywhere** (SQLite, espace disque limité). Projet en français : code commenté, UI et messages en français.

## Apps
- `accounts` : inscription/connexion, page d'accueil publique (`public_home`), context processor `discord_url`.
- `avent2026` : calendrier de l'Avent 2026 (voir section dédiée ci-dessous).
- `biblio` : mini-site indépendant.
- `mysite` : settings / urls. `templates/` : templates globaux (`home.html`, `base.html`, auth). `static/` : statiques globaux (`static/css/modern-*.css` pour l'accueil et l'auth).

## Contraintes d'hébergement et d'optimisation
- **Espace disque** : pas de gros fichiers dans le repo ni en `media/`. Images/GIF compressés (webp/jpg, idéalement < 200 Ko), aucune vidéo. Vérifier `du -sh` avant d'ajouter des assets.
- Peu de dépendances ; rien qui nécessite un process de fond (pas de Celery/Redis).
- SQLite : requêtes simples, `select_related`/`prefetch_related`, pas d'N+1, pas d'écritures lourdes concurrentes.
- Trafic faible (30 personnes) : pas de sur-ingénierie, pas de cache distribué.
- Le Django de PythonAnywhere est plus ancien que celui du dev (Python 3.10) : rester compatible Django 4.2 → 5.x (ex. `CheckConstraint(check=...)`, pas `condition=`) et tester aussi avec un venv Django 4.2 avant de pousser.
- `mysite/settings.py` est dans `.gitignore` mais déjà suivi par git ; la `SECRET_KEY` y est en dur et `DEBUG=True` : à sécuriser (variables d'environnement) avant d'y mettre quoi que ce soit de sensible.
- Ne pas committer `db.sqlite3`, `__pycache__`, `media/uploads`.

## Conventions d'une édition annuelle (Avent20XX)
- Une app par année, minimale au départ, nommée `avent20XX`, namespace d'URL `avent20XX`, templates dans `templates/avent20XX/`, statiques dans `static/avent20XX/`.
- Si on recrée un `UserProfile`, `related_name` suffixé par l'année (ex. `userprofile_2026`).
- Les CSS/images communs vont dans `static/`, pas dans l'app de l'année.
- Les anciennes éditions sont **supprimées** (elles restent dans l'historique git). Avant de retirer une app, ses tables sont supprimées par une migration : voir `accounts/migrations/0001_drop_legacy_avent_tables.py` (modèle à suivre ; faire un backup de `db.sqlite3` avant).

## Design (look « carnet de bord », sobre et professionnel)
- Fondations partagées dans `static/css/site.css` (variables de couleur, typo, en-tête, boutons, formulaires, pages publiques) ; styles du jeu dans `static/avent2026/css/avent.css`. `templates/_head.html` (métadonnées, polices, `site.css`) est inclus par toutes les pages : à réutiliser pour toute nouvelle page.
- Polices IBM Plex Sans (interface, chiffres tabulaires) et IBM Plex Serif (énoncés, histoire) chargées depuis Google Fonts ; pas de police à héberger.
- Une seule couleur d'accent d'interface (sapin `--sapin`) ; le laiton `--laiton` ne sert que dans la scène sombre (jour à jouer). Pas d'émojis comme icônes, pas de halos, pas de rebonds. Seule exception : sur les illustrations des villages, les lumières allumées ont une lueur douce (dégradé radial en `mix-blend-mode: screen`), jamais dans l'interface.
- Coordonnées décimales dans un template (positions de la scène) : toujours dans `{% localize off %}`, sinon la locale française écrit `41,5%` et le CSS devient invalide.

## Commandes
- Lancer : `python manage.py runserver` ; migrations : `python manage.py migrate` ; tests : `python manage.py test`.
- Déploiement PythonAnywhere : sauvegarder `db.sqlite3`, `git pull`, `python manage.py migrate`, `python manage.py collectstatic`, puis « Reload » de la web app. Dépendances : `pip install --user -r requirements.txt`. Onglet Web → Static files : `/static/` → `~/django-website/staticfiles` (et `/media/` → `~/django-website/media`). Après la première migration de nettoyage : `sqlite3 db.sqlite3 "VACUUM;"` pour récupérer l'espace.

- Hébergement sur Raspberry Pi (Pi 1 / Pi 3, Cloudflare Tunnel) : voir `DEPLOY_PI.md` (script d'installation automatique : `deploy/setup_pi.sh`).
- Production actuelle : **Pi 3 uniquement**, qui se met à jour seul depuis `main` (timer systemd `avent-update`, toutes les 5 min : `deploy/update_pi.sh`, installé par `deploy/install_autoupdate.sh`, doc en section 11 de `DEPLOY_PI.md`). Donc tout ce qui est fusionné dans `main` part en production en quelques minutes : CI GitHub (`.github/workflows/tests.yml`) à garder verte, migrations compatibles avec l'ancien code, et un commit qui touche `mysite/settings.py` bloque le déploiement automatique (config de prod locale en `skip-worktree`).

## avent2026 — architecture
- Deux pistes par jour : au plus une énigme et une devinette par jour (contrainte unique `(kind, day)`), pas de difficulté. Soit 24 énigmes + 24 devinettes.
- Modèles : `Puzzle` (kind enigme/devinette, jour 1-24), `Hint` (indices ordonnés, coût), `Attempt` (progression/points par joueur et puzzle), `HintReveal`. Pas de `UserProfile` : les scores se calculent depuis `Attempt`.
- Règles dans `avent2026/scoring.py` (points de base par type : énigme 100, devinette 50, coût d'indice, pénalité d'erreur, déblocage à minuit Europe/Paris, normalisation des réponses). Le staff voit tous les jours ; `AVENT2026_UNLOCK_ALL = True` dans settings débloque tout (tests/démo).
- Accueil : deux villages enneigés illustrés, un par piste (village des énigmes, village des devinettes), chacun avec 24 lumières (une par jour) posées sur l'illustration. Une image par village dans `static/avent2026/img/` (`village-enigmes.webp`, `village-devinettes.webp`, paysage 3:2, < 200 Ko, fenêtres éteintes) ; tant qu'elle manque, fond de nuit neigeuse en CSS. Position des lumières dans `avent2026/lights.json` (en % de l'image), réglée avec la page staff `/avent2026/calibrage/<enigme|devinette>/`. Cahier des charges des illustrations : `ILLUSTRATIONS_VILLAGES.md`. Pas de page « Jour » : chaque lumière renvoie directement vers son puzzle (`/avent2026/jour/<n>/` redirige vers l'accueil). L'épilogue s'affiche quand les puzzles publiés du jour 24 sont tous résolus. Styles dans `static/avent2026/css/avent.css`.
- **Exception : le village des devinettes est une carte étape par étape** (`village.CARTES`), plus de lumières posées sur l'image. 25 images `static/avent2026/img/carte-devinettes/village-iso-etape-00.webp` à `-24.webp` (1600×1080, ~2 Mo en tout) : l'image affichée est celle du **nombre de devinettes résolues par le joueur** (étape 0 = village sous la tempête). Les 24 jours sont des boutons sous l'image, dans le même cadre sombre (`.carte` / `.days` dans `avent.css`). Quand l'étape a augmenté depuis la dernière visite (clé de session `avent2026_carte_devinette`), la nouvelle image apparaît en fondu par-dessus l'ancienne, une seule fois. Les PNG d'origine ne sont pas versionnés (`.gitignore`). Le calibrage ne s'applique plus qu'au village des énigmes (`lights.json` garde des positions devinettes inutilisées).
- Contenu : via l'admin (`/admin/`), ou `python manage.py seed_avent2026` (contenu de test sur les jours 1 et 2, idempotent).
- Énoncés et indices rendus en HTML non échappé (`|safe`) : contenu saisi par l'admin uniquement.
- Tests : `python manage.py test avent2026`.
- Thème 2026 : une tempête a coupé le courant, deux villages voisins sont dans le noir et les joueurs (« les allumeurs ») rallument leurs lumières jusqu'à la place du réveillon, dont le grand sapin retrouve son étoile. `avent2026/village.py` : paliers (la progression se mesure en **lumières allumées = puzzles résolus, sur 48**, pas en points ; les points ne servent qu'au classement), prologue/épilogue, illustrations et positions des lumières. La neige se calme et l'image s'éclaircit avec la variable CSS `--calm` (0 à 1). `Puzzle.story` : fragment d'histoire révélé à la résolution (« ce qu'on voit par la fenêtre une fois allumée »), archivé dans le Journal (`/avent2026/journal/`). La date reste la seule porte d'entrée : aucun puzzle n'est bloqué par un échec.
