# 🚀 CHECKLIST DE DÉPLOIEMENT - Fix UserProfile

## ✅ Ce qui a été fait

### 1. Code modifié
- ✅ `avent2025/models.py` : Ajout signal automatique + fonction `get_or_create_profile()`
- ✅ `avent2025/views.py` : Utilisation de `get_or_create_profile()` dans toutes les vues
- ✅ Suppression des signaux en double

### 2. Outils créés
- ✅ `avent2025/management/commands/create_missing_profiles.py` : Commande Django
- ✅ `create_missing_profiles.py` : Script standalone
- ✅ `check_profiles.py` : Script de vérification
- ✅ `test_userprofile_fix.py` : Tests automatisés

### 3. Documentation
- ✅ `DEPLOYMENT_GUIDE_USERPROFILE.md` : Guide détaillé
- ✅ `FIX_USERPROFILE_SUMMARY.md` : Résumé de la solution
- ✅ `DEPLOYMENT_CHECKLIST.md` : Ce fichier

## 🎯 Actions à faire lors du déploiement

### Étape 1 : Mise à jour du code
```bash
cd /path/to/django-website
git pull origin main
```

### Étape 2 : Activation environnement
```bash
source django/bin/activate
```

### Étape 3 : Vérification migrations (si nécessaire)
```bash
python manage.py makemigrations
python manage.py migrate
```

### Étape 4 : **IMPORTANT** - Créer les profils manquants
```bash
python manage.py create_missing_profiles
```
⚠️ **Cette commande DOIT être exécutée pour que les utilisateurs existants puissent se connecter**

### Étape 5 : Vérification
```bash
python check_profiles.py
```

Vous devriez voir :
```
✅ X utilisateurs, X profils

  - user1: ✅ Profil OK
  - user2: ✅ Profil OK
  ...
```

### Étape 6 : Tests (optionnel mais recommandé)
```bash
python test_userprofile_fix.py
```

### Étape 7 : Redémarrage du serveur
```bash
# Si en développement
python manage.py runserver

# Si en production (exemple avec gunicorn)
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

## 🔍 Vérifications post-déploiement

### Test 1 : Connexion utilisateur existant
1. Aller sur `/accounts/login/`
2. Se connecter avec un utilisateur existant
3. ✅ La connexion doit réussir sans erreur
4. ✅ La page d'accueil `/avent2025/` doit s'afficher

### Test 2 : Nouvel utilisateur
1. Aller sur `/accounts/signup/`
2. Créer un nouveau compte
3. ✅ Le profil doit être créé automatiquement
4. ✅ L'utilisateur doit être redirigé vers `/avent2025/`

### Test 3 : Vérification database
```python
python manage.py shell

from django.contrib.auth.models import User
from avent2025.models import UserProfile

# Vérifier que chaque utilisateur a un profil
for user in User.objects.all():
    try:
        profile = user.userprofile_2025
        print(f"✅ {user.username}: Profil OK")
    except:
        print(f"❌ {user.username}: PAS DE PROFIL")
```

## ⚠️ En cas de problème

### Erreur : "User has no userprofile_2025" après déploiement

**Solution :**
```bash
python manage.py create_missing_profiles
```

### Erreur : "UNIQUE constraint failed: avent2025_userprofile.user_id"

**Cause :** Tentative de créer un profil qui existe déjà

**Solution :** Rien à faire, c'est normal si le profil existe déjà

### Un utilisateur spécifique n'a toujours pas de profil

**Solution manuelle via Django shell :**
```python
python manage.py shell

from django.contrib.auth.models import User
from avent2025.models import UserProfile

user = User.objects.get(username='nom_utilisateur')
UserProfile.objects.create(user=user)
```

## 📊 Commandes utiles

### Compter utilisateurs vs profils
```bash
python -c "import os; import django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings'); django.setup(); from django.contrib.auth.models import User; from avent2025.models import UserProfile; print(f'Users: {User.objects.count()}, Profiles: {UserProfile.objects.count()}')"
```

### Lister les utilisateurs sans profil
```bash
python -c "import os; import django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings'); django.setup(); from django.contrib.auth.models import User; [print(f'❌ {u.username}') for u in User.objects.all() if not hasattr(u, 'userprofile_2025')]"
```

## ✅ Validation finale

- [ ] Code mis à jour (`git pull`)
- [ ] Environnement activé
- [ ] Migrations appliquées
- [ ] **Commande `create_missing_profiles` exécutée**
- [ ] Vérification : tous les utilisateurs ont un profil
- [ ] Tests passent
- [ ] Serveur redémarré
- [ ] Test connexion utilisateur existant OK
- [ ] Test création nouvel utilisateur OK

## 📝 Notes importantes

1. **Les nouveaux utilisateurs** auront automatiquement un profil grâce au signal Django
2. **Les utilisateurs existants** doivent exécuter la commande `create_missing_profiles` UNE FOIS
3. La commande peut être réexécutée sans problème (elle ignore les profils existants)
4. Tous les scripts sont dans `/Users/damien/PersoLocal/django-website/`

## 📚 Références

- Guide détaillé : `DEPLOYMENT_GUIDE_USERPROFILE.md`
- Résumé technique : `FIX_USERPROFILE_SUMMARY.md`
- Tests : `test_userprofile_fix.py`
