"""
Tests pour vérifier que le système de UserProfile fonctionne correctement
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from avent2025.models import UserProfile, get_or_create_profile


def test_signal_creates_profile():
    """Test que le signal crée automatiquement un profil pour un nouvel utilisateur"""
    print("\n🧪 Test 1: Signal automatique lors de la création d'utilisateur")
    
    # Créer un utilisateur de test
    test_username = f"test_user_{User.objects.count()}"
    user = User.objects.create_user(username=test_username, password="testpass123")
    
    # Vérifier que le profil a été créé automatiquement
    assert hasattr(user, 'userprofile_2025'), "❌ Le profil n'a pas été créé automatiquement"
    assert user.userprofile_2025.currentEnigma == 0, "❌ Valeur initiale incorrecte"
    assert user.userprofile_2025.currentDevinette == 0, "❌ Valeur initiale incorrecte"
    
    # Nettoyer
    user.delete()
    
    print("   ✅ Le signal crée bien un profil automatiquement")


def test_get_or_create_profile():
    """Test que get_or_create_profile fonctionne correctement"""
    print("\n🧪 Test 2: Fonction get_or_create_profile()")
    
    # Créer un utilisateur sans profil (en désactivant temporairement le signal)
    from django.db.models.signals import post_save
    from avent2025.models import create_user_profile
    
    post_save.disconnect(create_user_profile, sender=User)
    
    test_username = f"test_user_no_profile_{User.objects.count()}"
    user = User.objects.create_user(username=test_username, password="testpass123")
    
    # Vérifier qu'il n'a pas de profil
    has_profile = hasattr(user, 'userprofile_2025')
    if has_profile:
        # Si le profil existe quand même, le supprimer pour le test
        user.userprofile_2025.delete()
    
    # Réactiver le signal
    post_save.connect(create_user_profile, sender=User)
    
    # Recharger l'utilisateur depuis la DB
    user = User.objects.get(username=test_username)
    
    # Utiliser get_or_create_profile
    profile = get_or_create_profile(user)
    
    assert profile is not None, "❌ get_or_create_profile a retourné None"
    assert hasattr(user, 'userprofile_2025'), "❌ Le profil n'a pas été créé"
    assert profile.currentEnigma == 0, "❌ Valeur initiale incorrecte"
    
    # Vérifier qu'appeler à nouveau ne crée pas de doublon
    profile2 = get_or_create_profile(user)
    assert profile.id == profile2.id, "❌ Un doublon a été créé"
    
    # Nettoyer
    user.delete()
    
    print("   ✅ get_or_create_profile fonctionne correctement")


def test_all_users_have_profiles():
    """Test que tous les utilisateurs actuels ont un profil"""
    print("\n🧪 Test 3: Vérification de tous les utilisateurs")
    
    users_without_profile = []
    for user in User.objects.all():
        if not hasattr(user, 'userprofile_2025'):
            users_without_profile.append(user.username)
    
    if users_without_profile:
        print(f"   ⚠️  Utilisateurs sans profil: {', '.join(users_without_profile)}")
        print("   💡 Exécutez: python manage.py create_missing_profiles")
        return False
    else:
        print(f"   ✅ Tous les {User.objects.count()} utilisateurs ont un profil")
        return True


def run_all_tests():
    """Exécute tous les tests"""
    print("=" * 60)
    print("🔬 TESTS DU SYSTÈME DE USERPROFILE")
    print("=" * 60)
    
    try:
        test_signal_creates_profile()
        test_get_or_create_profile()
        all_ok = test_all_users_have_profiles()
        
        print("\n" + "=" * 60)
        if all_ok:
            print("✅ TOUS LES TESTS RÉUSSIS!")
        else:
            print("⚠️  CERTAINS UTILISATEURS NÉCESSITENT UNE MIGRATION")
        print("=" * 60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}\n")
        raise


if __name__ == '__main__':
    run_all_tests()
