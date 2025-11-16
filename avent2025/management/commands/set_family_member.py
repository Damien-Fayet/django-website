"""
Commande Django pour gérer les membres de la famille.
Usage:
    python manage.py set_family_member <username> --add     # Ajouter à la famille
    python manage.py set_family_member <username> --remove  # Retirer de la famille
    python manage.py set_family_member --list               # Lister les membres
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from avent2025.models import UserProfile, get_or_create_profile


class Command(BaseCommand):
    help = 'Gère les membres de la famille dans le Calendrier de l\'Avent'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            nargs='?',
            type=str,
            help='Nom d\'utilisateur à modifier'
        )
        parser.add_argument(
            '--add',
            action='store_true',
            help='Ajouter l\'utilisateur à la famille'
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Retirer l\'utilisateur de la famille'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Lister tous les membres de la famille'
        )

    def handle(self, *args, **options):
        # Lister les membres
        if options['list']:
            self.list_family_members()
            return

        # Vérifier qu'un username est fourni pour add/remove
        username = options.get('username')
        if not username:
            self.stdout.write(self.style.ERROR('❌ Veuillez fournir un nom d\'utilisateur ou utiliser --list'))
            return

        # Vérifier que l'utilisateur existe
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ L\'utilisateur "{username}" n\'existe pas'))
            return

        # Garantir que le profil existe
        profile = get_or_create_profile(user)

        # Ajouter à la famille
        if options['add']:
            if profile.is_family:
                self.stdout.write(self.style.WARNING(f'⚠️  {username} est déjà membre de la famille'))
            else:
                profile.is_family = True
                profile.save()
                self.stdout.write(self.style.SUCCESS(f'✅ {username} a été ajouté à la famille'))

        # Retirer de la famille
        elif options['remove']:
            if not profile.is_family:
                self.stdout.write(self.style.WARNING(f'⚠️  {username} n\'est pas membre de la famille'))
            else:
                profile.is_family = False
                profile.save()
                self.stdout.write(self.style.SUCCESS(f'✅ {username} a été retiré de la famille'))

        else:
            self.stdout.write(self.style.ERROR('❌ Utilisez --add ou --remove'))

    def list_family_members(self):
        """Liste tous les membres de la famille"""
        family_profiles = UserProfile.objects.filter(is_family=True).select_related('user')
        
        if not family_profiles.exists():
            self.stdout.write(self.style.WARNING('⚠️  Aucun membre de la famille enregistré'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n👨‍👩‍👧‍👦 Membres de la famille ({family_profiles.count()}) :'))
        self.stdout.write('=' * 60)
        
        for profile in family_profiles:
            user = profile.user
            enigmes = f'Énigmes: {profile.currentEnigma}'
            devinettes = f'Devinettes: {profile.currentDevinette}'
            score = f'Score: {profile.score}'
            
            self.stdout.write(f'  • {user.username:20} | {enigmes:15} | {devinettes:18} | {score}')
        
        self.stdout.write('=' * 60)
