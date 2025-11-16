"""
Script pour créer les UserProfile manquants pour les utilisateurs existants
À exécuter une seule fois après le déploiement
"""
import os
import django

# Configuration de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from avent2025.models import UserProfile

def create_missing_profiles():
    """Crée les UserProfile pour tous les utilisateurs qui n'en ont pas"""
    users_without_profile = []
    profiles_created = 0
    
    for user in User.objects.all():
        if not hasattr(user, 'userprofile_2025'):
            users_without_profile.append(user.username)
            UserProfile.objects.create(user=user)
            profiles_created += 1
            print(f"✅ Profil créé pour l'utilisateur: {user.username}")
    
    if profiles_created > 0:
        print(f"\n🎉 {profiles_created} profil(s) créé(s) avec succès!")
        print(f"Utilisateurs concernés: {', '.join(users_without_profile)}")
    else:
        print("✅ Tous les utilisateurs ont déjà un profil!")
    
    return profiles_created

if __name__ == '__main__':
    print("🔍 Vérification des profils utilisateurs...\n")
    create_missing_profiles()
