"""
Commande Django pour créer les UserProfile manquants
Usage: python manage.py create_missing_profiles
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from avent2025.models import UserProfile


class Command(BaseCommand):
    help = 'Crée les UserProfile pour tous les utilisateurs qui n\'en ont pas'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('🔍 Vérification des profils utilisateurs...\n'))
        
        users_without_profile = []
        profiles_created = 0
        
        for user in User.objects.all():
            if not hasattr(user, 'userprofile_2025'):
                users_without_profile.append(user.username)
                UserProfile.objects.create(user=user)
                profiles_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Profil créé pour l\'utilisateur: {user.username}')
                )
        
        if profiles_created > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n🎉 {profiles_created} profil(s) créé(s) avec succès!')
            )
            self.stdout.write(
                self.style.WARNING(f'Utilisateurs concernés: {", ".join(users_without_profile)}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Tous les utilisateurs ont déjà un profil!')
            )
        
        return profiles_created
