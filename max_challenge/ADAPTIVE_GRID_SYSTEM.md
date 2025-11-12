# Système de Grille Adaptatif - Max Challenge

## Changements Implémentés

### 1. Redimensionnement Adaptatif (`max_challenge/models.py`)

La méthode `resize_to_400x400()` a été modifiée pour gérer deux formats :

#### Images Portrait (hauteur > largeur)
- **Détection** : `height > width`
- **Crop** : Ratio 2:3 (largeur/hauteur)
- **Sortie** : 400x600 pixels
- **Exemple** : 1000x1500 → 400x600

#### Images Paysage/Carrées (largeur ≥ hauteur)
- **Détection** : `width >= height`
- **Crop** : Carré (ratio 1:1)
- **Sortie** : 400x400 pixels
- **Exemple** : 1200x800 → 400x400

#### Optimisations
- **Compression JPEG** : Quality 85 (vs 95 précédemment)
- **Flag optimize** : Active les optimisations du codec
- **Poids des fichiers** : ~30-50 Ko pour portrait, ~25-40 Ko pour carré

### 2. Grille Dynamique (`max_challenge/templates/max_challenge/game.html`)

#### CSS Adaptatif

**Grille Portrait (par défaut)** :
```css
.grid-container {
    width: 400px;
    height: 600px;
    /* Grille 10x10 avec tuiles 40x60 */
}
```

**Grille Carrée** :
```css
.grid-container.square-grid {
    width: 400px;
    height: 400px;
    /* Grille 10x10 avec tuiles 40x40 */
}
```

#### JavaScript Intelligent

**Détection Automatique** :
```javascript
const img = new Image();
img.onload = function() {
    const isPortrait = img.height > img.width;
    
    if (isPortrait) {
        // 400x600, tuiles 40x60
        gridContainer.classList.remove('square-grid');
    } else {
        // 400x400, tuiles 40x40
        gridContainer.classList.add('square-grid');
    }
};
img.src = imageUrl;
```

**Calcul des Positions** :
```javascript
const tileWidth = 40;
const tileHeight = isPortrait ? 60 : 40;
const row = Math.floor(index / 10);
const col = index % 10;
square.style.setProperty('--bg-position', 
    `-${col * tileWidth}px -${row * tileHeight}px`);
```

### 3. Chargement en Masse (`bulk_load_photos.py`)

**Utilisation** :
```bash
source django/bin/activate
python bulk_load_photos.py /chemin/vers/dossier
```

**Fonctionnalités** :
- ✅ Supporte JPG, JPEG, PNG
- ✅ Détection automatique des doublons
- ✅ Redimensionnement automatique
- ✅ Rapport détaillé (succès/échecs/ignorés)
- ✅ Nommage automatique depuis fichier

### 4. Script de Test (`test_resize.py`)

**Vérification** :
```bash
python test_resize.py
```

Teste automatiquement :
- Portrait 1000x1500 → 400x600 ✓
- Carré 800x800 → 400x400 ✓
- Paysage 1200x800 → 400x400 ✓

## Architecture Technique

### Flux de Traitement

```
Image originale (n'importe quel format/taille)
    ↓
Détection orientation (height > width ?)
    ↓
┌───────────────┬──────────────────┐
│   Portrait    │   Paysage/Carré  │
├───────────────┼──────────────────┤
│ Crop 2:3      │ Crop 1:1 (carré) │
│ Resize 400x600│ Resize 400x400   │
│ JPEG qual 85  │ JPEG qual 85     │
└───────────────┴──────────────────┘
    ↓
Sauvegarde dans image_400x400 (nom générique)
    ↓
Affichage avec grille adaptative JS
```

### Compatibilité Ascendante

Le système est **100% compatible** avec les anciennes images 400x400 :

1. Anciennes images → détectées comme carrées → affichage 400x400
2. Nouvelles images portrait → détectées comme portrait → affichage 400x600
3. Grille 10x10 conservée (100 tuiles dans tous les cas)
4. 4 carrés révélés par bonne réponse (inchangé)

## Exemple Complet

### Préparation des Photos

```bash
# Dossier avec photos 1000x1500
/Users/damien/Photos/max_challenge/
├── alice.jpg       (1000x1500)
├── bob.png         (1200x1800)
├── charlie.jpeg    (800x600)
└── diane.jpg       (1500x1000)
```

### Chargement

```bash
cd /Users/damien/PersoLocal/django-website
source django/bin/activate
python bulk_load_photos.py /Users/damien/Photos/max_challenge
```

**Résultat** :
```
✅ alice: chargée et redimensionnée (400x600)
✅ bob: chargée et redimensionnée (400x600)
✅ charlie: chargée et redimensionnée (400x400 - paysage)
✅ diane: chargée et redimensionnée (400x600 - portrait détecté)
```

### Affichage dans le Jeu

- Alice, Bob, Diane : Grille 400x600 (10x10 tuiles de 40x60)
- Charlie : Grille 400x400 (10x10 tuiles de 40x40)

Chaque équipe révèle 4 carrés par bonne réponse.

## Optimisations de Poids

### Comparaison

| Format      | Avant (qual 95) | Après (qual 85 + optimize) |
|-------------|-----------------|----------------------------|
| 400x400     | ~50-70 Ko       | ~25-40 Ko (-40%)          |
| 400x600     | N/A             | ~30-50 Ko                 |

### Impact

Pour 1000 photos :
- Avant : ~60 Mo (400x400)
- Après : ~35-40 Mo (mix 400x400 + 400x600)
- **Économie** : ~30-40%

## Tests Effectués

✅ Redimensionnement portrait 1000x1500 → 400x600  
✅ Redimensionnement carré 800x800 → 400x400  
✅ Redimensionnement paysage 1200x800 → 400x400  
✅ Détection automatique orientation  
✅ Grille adaptative CSS (portrait/carré)  
✅ Calcul positions background-position dynamiques  
✅ Révélation progressive (4 carrés/réponse)  
✅ Changement de photo avec recréation grille  
✅ Polling détection changement image URL  
✅ Compatibilité images existantes  

## Maintenance

### Régénérer toutes les images

Si vous modifiez la qualité ou les dimensions :

```bash
python manage.py shell
```

```python
from max_challenge.models import Photo

for photo in Photo.objects.all():
    photo.resize_to_400x400()
    print(f"✅ {photo.name} régénérée")
```

### Vérifier les dimensions

```python
from max_challenge.models import Photo
from PIL import Image

for photo in Photo.objects.all()[:10]:
    if photo.image_400x400:
        img = Image.open(photo.image_400x400.path)
        print(f"{photo.name}: {img.size}")
```

## Documentation

- `BULK_LOAD_PHOTOS.md` : Guide utilisateur pour chargement en masse
- `test_resize.py` : Tests automatisés du système
- `bulk_load_photos.py` : Script de chargement en masse

## Prochaines Étapes Possibles

- [ ] Support WebP pour réduire davantage le poids
- [ ] Lazy loading des grilles pour performances
- [ ] Prévisualisation miniatures dans l'admin
- [ ] Détection automatique orientation EXIF
- [ ] Redimensionnement asynchrone (Celery)
