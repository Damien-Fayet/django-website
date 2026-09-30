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
- `mysite/settings.py` est dans `.gitignore` mais déjà suivi par git ; la `SECRET_KEY` y est en dur et `DEBUG=True` : à sécuriser (variables d'environnement) avant d'y mettre quoi que ce soit de sensible.
- Ne pas committer `db.sqlite3`, `__pycache__`, `media/uploads`.

## Conventions d'une édition annuelle (Avent20XX)
- Une app par année, minimale au départ, nommée `avent20XX`, namespace d'URL `avent20XX`, templates dans `templates/avent20XX/`, statiques dans `static/avent20XX/`.
- Si on recrée un `UserProfile`, `related_name` suffixé par l'année (ex. `userprofile_2026`).
- Les CSS/images communs vont dans `static/`, pas dans l'app de l'année.
- Les anciennes éditions sont **supprimées** (elles restent dans l'historique git). Avant de retirer une app, ses tables sont supprimées par une migration : voir `accounts/migrations/0001_drop_legacy_avent_tables.py` (modèle à suivre ; faire un backup de `db.sqlite3` avant).

## Commandes
- Lancer : `python manage.py runserver` ; migrations : `python manage.py migrate` ; tests : `python manage.py test`.
- Déploiement PythonAnywhere : sauvegarder `db.sqlite3`, `git pull`, `python manage.py migrate`, `python manage.py collectstatic`, puis « Reload » de la web app. Après la première migration de nettoyage : `sqlite3 db.sqlite3 "VACUUM;"` pour récupérer l'espace.

## avent2026 — architecture
- Modèles : `Puzzle` (kind enigme/devinette, jour 1-24, difficulté facile/difficile), `Hint` (indices ordonnés, coût), `Attempt` (progression/points par joueur et puzzle), `HintReveal`. Pas de `UserProfile` : les scores se calculent depuis `Attempt`.
- Règles dans `avent2026/scoring.py` (points de base par type/difficulté, coût d'indice, pénalité d'erreur, déblocage à minuit Europe/Paris, normalisation des réponses). Le staff voit tous les jours ; `AVENT2026_UNLOCK_ALL = True` dans settings débloque tout (tests/démo).
- Scène d'accueil non linéaire : `avent2026/scene.py` (positions des 24 jours, paysage/portrait) + `static/avent2026/css/avent.css`. Décor et thème à définir ; aucune image pour l'instant.
- Contenu : via l'admin (`/admin/`), ou `python manage.py seed_avent2026` (contenu de test sur les jours 1 et 2, idempotent).
- Énoncés et indices rendus en HTML non échappé (`|safe`) : contenu saisi par l'admin uniquement.
- Tests : `python manage.py test avent2026`.
- Thème 2026 : un petit robot apprend et s'améliore pour rejoindre le Père Noël. `avent2026/robot.py` : niveaux/modules (énergie = total des points), prologue/épilogue ; `scene.py` : 4 zones de 6 jours ; `templates/avent2026/_robot.html` : robot en SVG inline (modules affichés selon le niveau) ; `Puzzle.story` : fragment d'histoire révélé à la résolution, archivé dans le Journal (`/avent2026/journal/`). La date reste la seule porte d'entrée : aucun puzzle n'est bloqué par un échec.
