# 🎯 Configuration du Système de Score - Calendrier de l'Avent 2025

## Vue d'ensemble

Le système de score du calendrier de l'avent est maintenant **entièrement paramétrable**. Vous pouvez ajuster les points gagnés et les malus selon vos préférences.

## Configuration par défaut

| Élément | Points |
|---------|--------|
| 🧩 Énigme résolue | **+100 points** |
| 🎭 Devinette résolue | **+10 points** |
| ❌ Erreur d'énigme | **-10 points** |
| ❌ Erreur de devinette | **-2 points** |

## Formule de calcul

```
Score Total = (Énigmes résolues × Points énigme) 
            - (Erreurs énigmes × Malus énigme)
            + (Devinettes résolues × Points devinette)
            - (Erreurs devinettes × Malus devinette)
```

### Exemple

Un joueur avec :
- 3 énigmes résolues
- 5 devinettes résolues
- 2 erreurs d'énigmes
- 3 erreurs de devinettes

**Calcul :**
```
Score = (3 × 100) - (2 × 10) + (5 × 10) - (3 × 2)
      = 300 - 20 + 50 - 6
      = 324 points
```

## Méthodes de modification

### 1️⃣ Via l'interface Admin Django (Recommandé)

1. Connectez-vous à l'admin : `/admin/`
2. Allez dans **Avent2025** → **Configuration des scores**
3. Modifiez les valeurs selon vos besoins
4. Cliquez sur **Enregistrer**

✨ **Avantages :**
- Interface visuelle conviviale
- Validation automatique des données
- Descriptions d'aide pour chaque champ
- Impossible de créer plusieurs configurations (singleton)

### 2️⃣ Via la ligne de commande

```bash
# Afficher la configuration actuelle
python manage.py config_scores --show

# Modifier les points par énigme
python manage.py config_scores --enigme 150

# Modifier les points par devinette
python manage.py config_scores --devinette 15

# Modifier le malus d'erreur d'énigme
python manage.py config_scores --malus-enigme 15

# Modifier le malus d'erreur de devinette
python manage.py config_scores --malus-devinette 3

# Modifier plusieurs valeurs en une seule fois
python manage.py config_scores --enigme 120 --devinette 12 --malus-enigme 12 --malus-devinette 3
```

✨ **Avantages :**
- Rapide pour des modifications ponctuelles
- Scriptable (automatisation possible)
- Affiche un exemple de calcul avec les nouvelles valeurs

## Scénarios d'utilisation

### 🎮 Mode Facile (encourager les joueurs)

```bash
python manage.py config_scores --enigme 200 --devinette 20 --malus-enigme 5 --malus-devinette 1
```

**Résultat :** Plus de points, moins de pénalités

### 🔥 Mode Difficile (compétition)

```bash
python manage.py config_scores --enigme 100 --devinette 5 --malus-enigme 25 --malus-devinette 5
```

**Résultat :** Pénalités sévères pour les erreurs

### ⚖️ Mode Équilibré (par défaut)

```bash
python manage.py config_scores --enigme 100 --devinette 10 --malus-enigme 10 --malus-devinette 2
```

**Résultat :** Équilibre entre récompenses et pénalités

### 🎯 Mode "Devinettes importantes"

```bash
python manage.py config_scores --enigme 50 --devinette 50 --malus-enigme 10 --malus-devinette 10
```

**Résultat :** Énigmes et devinettes valent autant

## Impact sur le classement

⚠️ **Important :** Les modifications de configuration affectent **immédiatement** le classement de tous les joueurs.

Le classement est recalculé dynamiquement à chaque affichage avec la formule actuelle, donc :
- ✅ Les changements sont appliqués en temps réel
- ✅ Pas besoin de recalculer manuellement les scores
- ✅ Tous les joueurs sont affectés de la même manière

## Limitations et sécurité

### Singleton Pattern
- ✅ Une seule configuration possible
- ✅ Impossible de créer plusieurs configurations
- ✅ Impossible de supprimer la configuration (protection)

### Validation
- Les valeurs doivent être des nombres entiers
- Pas de limite min/max (vous pouvez mettre des valeurs négatives si vous voulez pénaliser la réussite !)

## Conseils pratiques

### 📊 Avant de modifier

1. **Notez la configuration actuelle** avec `--show`
2. **Testez** sur un environnement de développement si possible
3. **Informez les joueurs** des changements de scoring

### 🔄 Réinitialiser aux valeurs par défaut

```bash
python manage.py config_scores --enigme 100 --devinette 10 --malus-enigme 10 --malus-devinette 2
```

### 📈 Analyser l'impact

Après modification, vérifiez le classement pour voir l'impact :
- Allez sur `/avent2025/leaderboard/`
- Comparez les positions avant/après

## Support technique

En cas de problème :
1. Vérifiez que la migration est appliquée : `python manage.py migrate`
2. Vérifiez la configuration : `python manage.py config_scores --show`
3. Consultez les logs Django pour les erreurs

## Développeurs : Utilisation dans le code

```python
from avent2025.models import ScoreConfig

# Récupérer la configuration
config = ScoreConfig.get_config()

# Utiliser les valeurs
points = config.points_enigme_resolue
malus = config.malus_erreur_enigme

# Calculer un score
score = (enigmes * config.points_enigme_resolue - 
         erreurs_enigmes * config.malus_erreur_enigme +
         devinettes * config.points_devinette_resolue -
         erreurs_devinettes * config.malus_erreur_devinette)
```

## Historique des versions

- **v1.0** (16 nov 2025) : Système de score paramétrable implémenté
  - Modèle ScoreConfig créé
  - Interface admin ajoutée
  - Commande de gestion créée
  - Intégration dans le leaderboard
