# Calendrier de l'Avent 2025 - Documentation

## 🎄 Présentation

Le projet **avent2025** est une duplication complète du projet **avent2024**, créé pour l'édition 2025 du calendrier de l'Avent. Il permet aux utilisateurs de résoudre des énigmes et des devinettes tout au long du mois de décembre.

## 📋 Modifications apportées

### 1. Structure du projet
- **Duplication** : Copie complète du dossier `avent2024` vers `avent2025`
- **Fichiers modifiés** :
  - `apps.py` : Renommage de `Avent2024Config` en `Avent2025Config`
  - `models.py` : Mise à jour des dates par défaut (2024 → 2025)
  - `views.py` : Adaptation de toutes les références
  - `urls.py` : Changement du namespace `avent2024` → `avent2025`
  - `admin.py` : Mise à jour des imports

### 2. Modifications critiques des modèles

#### UserProfile
Pour éviter les conflits avec avent2024, le modèle UserProfile utilise maintenant :
```python
user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile_2025')
```

**Important** : Dans le code, utiliser `request.user.userprofile_2025` au lieu de `request.user.userprofile`

#### Signals
Les fonctions de signal ont été renommées :
- `create_user_profile` → `create_user_profile_2025`
- `save_user_profile` → `save_user_profile_2025`

### 3. Templates et fichiers statiques

#### Répertoires renommés
- `templates/avent2024/` → `templates/avent2025/`
- `static/avent2024/` → `static/avent2025/`

#### Template tags
Pour éviter les conflits :
- `customfilters.py` → `customfilters2025.py`
- Dans les templates : `{% load customfilters %}` → `{% load customfilters2025 %}`

### 4. Configuration Django

#### settings.py
Ajout dans `INSTALLED_APPS` :
```python
"avent2025.apps.Avent2025Config",
```

#### urls.py (mysite)
Nouvelle route ajoutée :
```python
path("avent2025/", include("avent2025.urls")),
```

### 5. Menu principal (home.html)
Ajout de 2 nouvelles tuiles :
- 🧩 **Énigmes 2025** : `/avent2025/avent2025`
- 🎭 **Devinettes 2025** : `/avent2025/avent2025_devinette`

## 🔗 URLs disponibles

### Projet avent2025
- `/avent2025/` - Page d'accueil énigmes
- `/avent2025/avent2025` - Page d'accueil énigmes
- `/avent2025/avent2025_devinette` - Page d'accueil devinettes
- `/avent2025/display_enigme/` - Affichage d'une énigme
- `/avent2025/display_devinette/` - Affichage d'une devinette
- `/avent2025/start_adventure/` - Démarrer les énigmes
- `/avent2025/start_devinette/` - Démarrer les devinettes
- `/avent2025/validate_enigme/` - Valider une réponse d'énigme
- `/avent2025/validate_devinette/` - Valider une réponse de devinette
- `/avent2025/reveler_indice/` - Révéler un indice d'énigme
- `/avent2025/reveler_indice_devinette/` - Révéler un indice de devinette
- `/avent2025/classement/` - Classement des joueurs
- `/avent2025/all_enigmes/` - Liste de toutes les énigmes

## 📊 Base de données

### Nouvelles tables créées
- `avent2025_userprofile`
- `avent2025_enigme`
- `avent2025_devinette`
- `avent2025_indice`
- `avent2025_indicedevinette`

### Migration initiale
```bash
python manage.py makemigrations avent2025
python manage.py migrate avent2025
```

## ⚠️ Points d'attention

### 1. Données séparées
Les projets avent2024 et avent2025 ont des bases de données **séparées** :
- Les profils utilisateurs sont distincts (`userprofile` vs `userprofile_2025`)
- Les énigmes et devinettes sont stockées dans des tables différentes
- Les scores et progressions sont indépendants

### 2. Administration Django
Dans l'admin Django (`/admin/`), vous trouverez :
- Les modèles pour avent2024 (UserProfile, Enigme, Devinette, etc.)
- Les modèles pour avent2025 (mêmes noms mais tables différentes)

### 3. Dates par défaut
Les dates par défaut dans les modèles ont été mises à jour :
- `date_dispo = models.DateField(default="2025-11-02")`

N'oubliez pas de mettre à jour ces dates selon le calendrier réel de l'Avent 2025.

## 🚀 Prochaines étapes

1. **Créer du contenu** :
   - Ajouter des énigmes via l'admin Django
   - Ajouter des devinettes via l'admin Django
   - Ajouter des indices pour chaque énigme/devinette

2. **Personnaliser** :
   - Modifier les images dans `static/avent2025/images/`
   - Adapter les styles CSS dans `static/avent2025/css/`
   - Mettre à jour les textes dans les templates

3. **Tester** :
   - Créer un compte utilisateur de test
   - Vérifier le fonctionnement des énigmes
   - Vérifier le fonctionnement des devinettes
   - Tester le système d'indices
   - Vérifier le classement

## 🛠️ Commandes utiles

```bash
# Activer l'environnement virtuel
source django/bin/activate

# Lancer le serveur de développement
python manage.py runserver

# Créer un superutilisateur (si nécessaire)
python manage.py createsuperuser

# Collecter les fichiers statiques (pour production)
python manage.py collectstatic
```

## 📝 Notes

- Le projet est pleinement fonctionnel et indépendant d'avent2024
- Les deux projets peuvent coexister sans problème
- Les utilisateurs peuvent participer aux deux calendriers en parallèle
- Chaque calendrier a sa propre progression et son propre classement
