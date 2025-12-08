"""
Script de migration pour pré-remplir les réponses validées des utilisateurs.
À exécuter AVANT la mise en production du nouveau système de résolution flexible.

Ce script reconstruit les dictionnaires reponses_enigmes et reponses_devinettes
en se basant sur currentEnigma et currentDevinette.

Usage:
    python manage.py shell < migrate_user_responses.py
    ou
    python migrate_user_responses.py
"""

import os
import sys
import django

# Configuration Django
if __name__ == '__main__':
    # Ajouter le répertoire parent au path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
    django.setup()

from avent2025.models import UserProfile, Enigme, Devinette
from django.contrib.auth.models import User


def migrate_user_responses():
    """
    Migre les données existantes des utilisateurs pour remplir reponses_enigmes et reponses_devinettes.
    """
    print("=" * 80)
    print("MIGRATION DES RÉPONSES UTILISATEURS")
    print("=" * 80)
    
    # Récupérer tous les profils utilisateurs
    profiles = UserProfile.objects.all()
    total = profiles.count()
    migrated_count = 0
    already_migrated_count = 0
    
    print(f"\n📊 Total de profils à analyser : {total}")
    print("\n" + "-" * 80)
    
    for profile in profiles:
        user = profile.user
        username = user.username
        changes = []
        
        # ===== ÉNIGMES =====
        # Si currentEnigma > 1, cela signifie que l'utilisateur a résolu des énigmes
        if profile.currentEnigma > 1:
            # Vérifier si reponses_enigmes est vide ou manque des entrées
            existing_responses = profile.reponses_enigmes or {}
            enigmes_a_ajouter = []
            
            for enigme_id in range(1, profile.currentEnigma):
                enigme_id_str = str(enigme_id)
                if enigme_id_str not in existing_responses:
                    # Récupérer la vraie réponse de l'énigme
                    try:
                        enigme = Enigme.objects.get(id=enigme_id)
                        existing_responses[enigme_id_str] = enigme.reponse
                        enigmes_a_ajouter.append(enigme_id)
                    except Enigme.DoesNotExist:
                        print(f"⚠️  Énigme {enigme_id} n'existe pas dans la base")
            
            if enigmes_a_ajouter:
                profile.reponses_enigmes = existing_responses
                changes.append(f"Énigmes ajoutées : {enigmes_a_ajouter}")
        
        # ===== DEVINETTES =====
        # Si currentDevinette > 1, cela signifie que l'utilisateur a résolu des devinettes
        if profile.currentDevinette > 1:
            # Vérifier si reponses_devinettes est vide ou manque des entrées
            existing_responses = profile.reponses_devinettes or {}
            devinettes_a_ajouter = []
            
            for devinette_id in range(1, profile.currentDevinette):
                devinette_id_str = str(devinette_id)
                if devinette_id_str not in existing_responses:
                    # Récupérer la vraie réponse de la devinette
                    try:
                        devinette = Devinette.objects.get(id=devinette_id)
                        existing_responses[devinette_id_str] = devinette.reponse
                        devinettes_a_ajouter.append(devinette_id)
                    except Devinette.DoesNotExist:
                        print(f"⚠️  Devinette {devinette_id} n'existe pas dans la base")
            
            if devinettes_a_ajouter:
                profile.reponses_devinettes = existing_responses
                changes.append(f"Devinettes ajoutées : {devinettes_a_ajouter}")
        
        # Sauvegarder si des changements ont été faits
        if changes:
            profile.save()
            migrated_count += 1
            print(f"✅ {username} (currentEnigma={profile.currentEnigma}, currentDevinette={profile.currentDevinette})")
            for change in changes:
                print(f"   → {change}")
        else:
            already_migrated_count += 1
    
    print("\n" + "-" * 80)
    print("\n📈 RÉSUMÉ DE LA MIGRATION")
    print(f"   Total de profils analysés : {total}")
    print(f"   ✅ Profils migrés : {migrated_count}")
    print(f"   ℹ️  Profils déjà à jour : {already_migrated_count}")
    print("\n" + "=" * 80)
    
    # Vérification finale
    print("\n🔍 VÉRIFICATION FINALE")
    print("-" * 80)
    
    issues_found = 0
    for profile in UserProfile.objects.all():
        # Vérifier la cohérence
        reponses_enigmes_count = len(profile.reponses_enigmes) if profile.reponses_enigmes else 0
        reponses_devinettes_count = len(profile.reponses_devinettes) if profile.reponses_devinettes else 0
        
        expected_enigmes = max(0, profile.currentEnigma - 1) if profile.currentEnigma > 0 else 0
        expected_devinettes = max(0, profile.currentDevinette - 1) if profile.currentDevinette > 0 else 0
        
        if reponses_enigmes_count != expected_enigmes or reponses_devinettes_count != expected_devinettes:
            issues_found += 1
            print(f"⚠️  {profile.user.username}:")
            print(f"   Énigmes: {reponses_enigmes_count} réponses vs {expected_enigmes} attendues (currentEnigma={profile.currentEnigma})")
            print(f"   Devinettes: {reponses_devinettes_count} réponses vs {expected_devinettes} attendues (currentDevinette={profile.currentDevinette})")
    
    if issues_found == 0:
        print("✅ Aucune incohérence détectée - tous les profils sont corrects!")
    else:
        print(f"\n⚠️  {issues_found} profil(s) avec des incohérences détectées")
    
    print("=" * 80)
    print("✅ MIGRATION TERMINÉE")
    print("=" * 80)


if __name__ == '__main__':
    # Demander confirmation avant d'exécuter
    print("\n⚠️  ATTENTION ⚠️")
    print("Ce script va modifier les données des utilisateurs en pré-remplissant")
    print("les dictionnaires reponses_enigmes et reponses_devinettes.")
    print("\nIl est recommandé de faire une sauvegarde de la base de données avant.")
    
    response = input("\nVoulez-vous continuer ? (oui/non) : ")
    
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        migrate_user_responses()
    else:
        print("\n❌ Migration annulée")
