# Chargement en Masse de Photos - Max Challenge

## Vue d'ensemble

Ce système permet de charger en masse des photos pour le jeu Max Challenge. Les images sont automatiquement redimensionnées selon leur orientation :

- **Images portrait** (1000x1500, etc.) → 400x600 pixels (ratio 2:3)
- **Images paysage/carrées** → 400x400 pixels (carré)

## Formats supportés

- `.jpg` / `.jpeg`
- `.png`

Les images sont automatiquement converties en JPEG avec compression optimisée (quality=85, optimize=True).

## Utilisation du Script

### 1. Préparation

Placez toutes vos photos dans un dossier. Le nom du fichier (sans extension) sera utilisé comme nom de la photo dans le jeu.

**Exemple :**
```
/Users/damien/Photos/max_challenge/
├── alice.jpg
├── bob.png
├── charlie.jpeg
└── diane.jpg
```

Les photos seront créées avec les noms : "alice", "bob", "charlie", "diane".

### 2. Activation de l'environnement

```bash
source django/bin/activate
```

### 3. Exécution du script

```bash
python bulk_load_photos.py /chemin/vers/dossier/photos
```

**Exemple concret :**
```bash
python bulk_load_photos.py /Users/damien/Photos/max_challenge
```

### 4. Résultat

Le script affiche :
- ✅ Photos chargées avec succès
- ⏭️ Photos déjà existantes (ignorées)
- ❌ Erreurs rencontrées

**Exemple de sortie :**
```
📁 45 images trouvées dans /Users/damien/Photos/max_challenge
🚀 Début du chargement...

✅ alice: chargée et redimensionnée
✅ bob: chargée et redimensionnée
⏭️ charlie: déjà existante, ignorée
✅ diane: chargée et redimensionnée
...

============================================================
📊 RÉSUMÉ DU CHARGEMENT
============================================================
✅ Succès:  42 photos
⏭️ Ignorées: 3 photos (déjà existantes)
❌ Erreurs:  0 photos
📁 Total:    45 fichiers traités
============================================================
```

## Redimensionnement Automatique

### Images Portrait (hauteur > largeur)

Les images sont détectées automatiquement et redimensionnées en **400x600 pixels** :

1. L'image est croppée pour obtenir un ratio 2:3
2. Redimensionnée à 400x600
3. Compressée en JPEG (quality=85, optimize=True)

**Exemple :** Une photo 1000x1500 px → 400x600 px (~30-50 Ko)

### Images Paysage/Carrées

Les images sont croppées en carré puis redimensionnées en **400x400 pixels**.

**Exemple :** Une photo 1200x800 px → 400x400 px (~25-40 Ko)

## Affichage dans le Jeu

La grille s'adapte automatiquement :

- **Portrait (400x600)** : Grille 10x10 avec tuiles de 40x60 pixels
- **Carré (400x400)** : Grille 10x10 avec tuiles de 40x40 pixels

Le système détecte automatiquement l'orientation de chaque photo et ajuste l'affichage en conséquence.

## Gestion des Doublons

- Si une photo avec le même nom existe déjà, elle est **ignorée** (pas écrasée)
- Pour remplacer une photo, supprimez-la d'abord dans l'interface d'administration Django

## Optimisations

- **Compression JPEG** : Quality=85 (bon équilibre qualité/poids)
- **Optimize flag** : Active les optimisations du codec JPEG
- **Conversion RGB** : Toutes les images sont converties en RGB (compatibilité JPEG)

## Vérification

Pour vérifier les photos chargées, accédez à l'interface d'administration Django :

```
http://localhost:8000/admin/max_challenge/photo/
```

## Commandes Utiles

### Compter les photos en base

```bash
python manage.py shell
>>> from max_challenge.models import Photo
>>> Photo.objects.count()
```

### Supprimer toutes les photos (ATTENTION !)

```bash
python manage.py shell
>>> from max_challenge.models import Photo
>>> Photo.objects.all().delete()
```

### Relancer le redimensionnement pour toutes les photos

```bash
python manage.py shell
>>> from max_challenge.models import Photo
>>> for photo in Photo.objects.all():
...     photo.resize_to_400x400()
```

## Dépannage

### "Module max_challenge not found"

Vérifiez que vous êtes dans le bon dossier et que l'environnement virtuel est activé :

```bash
cd /Users/damien/PersoLocal/django-website
source django/bin/activate
```

### "Image file is truncated"

Le fichier image est corrompu. Supprimez-le du dossier source et réessayez.

### "Permission denied"

Assurez-vous que le serveur Django n'utilise pas les fichiers. Arrêtez le serveur pendant le chargement en masse.

## Performance

- **Temps de traitement** : ~0.5-1 seconde par image (redimensionnement inclus)
- **45 photos** : ~30-45 secondes
- **1000 photos** : ~10-15 minutes

Le script affiche la progression en temps réel.
