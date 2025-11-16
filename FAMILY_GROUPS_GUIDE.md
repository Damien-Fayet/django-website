# 👨‍👩‍👧‍👦 Système de Groupes Famille - Calendrier de l'Avent 2025

## Vue d'ensemble

Le système permet de distinguer les membres de votre famille des utilisateurs publics lambda. Cela vous permet de créer des classements séparés et de personnaliser l'expérience.

## Fonctionnalités

### 1. Champ `is_family` dans UserProfile

Chaque utilisateur a maintenant un champ booléen `is_family` qui indique s'il fait partie de la famille.

- **Par défaut** : `False` (utilisateur public)
- **Modifiable** : Via l'admin Django ou la commande de gestion

### 2. Commande de gestion `set_family_member`

#### Ajouter un membre à la famille
```bash
python manage.py set_family_member <username> --add
```

Exemple :
```bash
python manage.py set_family_member damien --add
python manage.py set_family_member marie --add
python manage.py set_family_member paul --add
```

#### Retirer un membre de la famille
```bash
python manage.py set_family_member <username> --remove
```

Exemple :
```bash
python manage.py set_family_member paul --remove
```

#### Lister tous les membres de la famille
```bash
python manage.py set_family_member --list
```

Affiche :
- Nombre total de membres de la famille
- Liste détaillée avec username, progression énigmes/devinettes et score

### 3. Page Classement avec Filtres

URL : `/avent2025/leaderboard/`

#### Filtres disponibles :
- **Tous** (`?filter=all`) : Affiche tous les joueurs
- **Famille** (`?filter=family`) : Uniquement les membres de la famille
- **Public** (`?filter=public`) : Uniquement les utilisateurs publics

#### Fonctionnalités du classement :
- 🏆 Badges spéciaux pour les 3 premiers (or, argent, bronze)
- 👨‍👩‍👧‍👦 Badge "Famille" visible pour les membres de la famille
- ⬅️ Mise en évidence de votre position
- 📊 Statistiques en temps réel
- 🎯 Score calculé automatiquement

#### Calcul du score :
```
Score = (Énigmes résolues × 100) - (Erreurs énigmes × 10) 
        + (Devinettes résolues × 10) - (Erreurs devinettes × 2)
```

### 4. Administration Django

Dans l'admin Django (`/admin/`), vous pouvez :
1. Aller dans "Users"
2. Sélectionner un utilisateur
3. Dans la section "User Profile", cocher/décocher "Membre de la famille"

## Cas d'usage

### Scénario 1 : Classement famille uniquement
Vous voulez voir comment votre famille se classe entre elle :
```
/avent2025/leaderboard/?filter=family
```

### Scénario 2 : Comparer famille vs public
1. Afficher le classement famille
2. Puis afficher le classement public
3. Comparer les performances

### Scénario 3 : Classement global
Voir où se situent les membres de la famille parmi tous les joueurs :
```
/avent2025/leaderboard/?filter=all
```

## Migration des utilisateurs existants

Tous les utilisateurs existants sont automatiquement marqués comme `is_family=False`.

Pour migrer vos utilisateurs existants vers la famille :
```bash
# Marquer tous vos proches
python manage.py set_family_member maman --add
python manage.py set_family_member papa --add
python manage.py set_family_member soeur --add
python manage.py set_family_member frere --add

# Vérifier
python manage.py set_family_member --list
```

## Interface utilisateur

### Badge "Famille"
Les membres de la famille ont un badge violet visible dans :
- Le classement
- (Peut être étendu à d'autres pages si besoin)

### Statistiques
Le classement affiche :
- Nombre total de joueurs
- Nombre de membres de la famille
- Nombre d'utilisateurs publics

## Personnalisation future

Le système est extensible pour :
- Créer plusieurs groupes (amis, collègues, etc.)
- Ajouter des récompenses spéciales pour la famille
- Créer des défis famille vs public
- Envoyer des notifications spécifiques

## Notes techniques

### Modèle
```python
class UserProfile(models.Model):
    # ... autres champs
    is_family = models.BooleanField(
        default=False, 
        verbose_name="Membre de la famille",
        help_text="Cochez pour marquer cet utilisateur comme membre de la famille"
    )
```

### Migration
Fichier : `avent2025/migrations/0004_userprofile_is_family.py`

Cette migration ajoute le champ `is_family` avec la valeur par défaut `False` pour tous les utilisateurs existants.

## Support

Pour toute question ou problème :
1. Vérifier que la migration est appliquée : `python manage.py migrate`
2. Vérifier les membres : `python manage.py set_family_member --list`
3. Accéder au classement : `/avent2025/leaderboard/`
