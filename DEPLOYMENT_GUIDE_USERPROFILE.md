# Guide de déploiement - Calendrier de l'Avent 2025

## Problème résolu : UserProfile manquant

### Symptôme
Erreur `User has no userprofile_2025` lors de la connexion d'utilisateurs existants.

### Cause
Les utilisateurs créés avant la mise en place du système de profils automatiques n'ont pas de UserProfile associé.

### Solution mise en place

#### 1. Signal automatique pour les nouveaux utilisateurs
Un signal Django a été ajouté dans `avent2025/models.py` qui crée automatiquement un UserProfile à chaque création d'utilisateur :

```python
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée automatiquement un UserProfile quand un User est créé"""
    if created:
        UserProfile.objects.create(user=instance)
```

#### 2. Fonction utilitaire de sécurité
Une fonction `get_or_create_profile(user)` a été ajoutée qui garantit qu'un profil existe :

```python
def get_or_create_profile(user):
    """Fonction utilitaire pour garantir qu'un UserProfile existe"""
    if not hasattr(user, 'userprofile_2025'):
        UserProfile.objects.create(user=user)
    return user.userprofile_2025
```

Cette fonction est maintenant utilisée dans toutes les vues pour éviter l'erreur.

#### 3. Commande de migration pour utilisateurs existants

**Option 1 - Script Python standalone :**
```bash
python create_missing_profiles.py
```

**Option 2 - Commande Django (recommandée) :**
```bash
python manage.py create_missing_profiles
```

### Procédure de déploiement

#### Étape 1 : Mettre à jour le code
```bash
git pull origin main
```

#### Étape 2 : Activer l'environnement virtuel
```bash
source django/bin/activate
```

#### Étape 3 : Appliquer les migrations
```bash
python manage.py migrate
```

#### Étape 4 : Créer les profils manquants
```bash
python manage.py create_missing_profiles
```

#### Étape 5 : Redémarrer le serveur
```bash
# Arrêter le serveur actuel (Ctrl+C)
# Relancer
python manage.py runserver
```

### Vérification

Pour vérifier que tous les utilisateurs ont un profil :

```python
from django.contrib.auth.models import User
from avent2025.models import UserProfile

# Compter les utilisateurs
total_users = User.objects.count()
total_profiles = UserProfile.objects.count()

print(f"Utilisateurs: {total_users}")
print(f"Profils: {total_profiles}")

# Lister les utilisateurs sans profil
for user in User.objects.all():
    if not hasattr(user, 'userprofile_2025'):
        print(f"⚠️ {user.username} n'a pas de profil")
```

### Points importants

1. **Les nouveaux utilisateurs** créés après le déploiement auront automatiquement un profil grâce au signal
2. **Les utilisateurs existants** doivent exécuter la commande `create_missing_profiles` une fois
3. **Toutes les vues** utilisent désormais `get_or_create_profile()` pour plus de sécurité
4. **Aucune perte de données** - le script crée uniquement les profils manquants avec les valeurs par défaut

### En cas de problème

Si un utilisateur rencontre toujours l'erreur après le déploiement :

1. Vérifier dans Django Admin si l'utilisateur a un UserProfile
2. Créer manuellement le profil si nécessaire :
   ```python
   from django.contrib.auth.models import User
   from avent2025.models import UserProfile
   
   user = User.objects.get(username='nom_utilisateur')
   UserProfile.objects.create(user=user)
   ```
3. Ou réexécuter la commande : `python manage.py create_missing_profiles`

### Maintenance future

- Le signal garantit que tous les nouveaux utilisateurs auront un profil
- La fonction `get_or_create_profile()` offre une double sécurité dans les vues
- La commande `create_missing_profiles` peut être réexécutée sans danger (elle ignore les profils existants)
