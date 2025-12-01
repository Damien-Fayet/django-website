from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from avent2025.models import UserProfile, Indice, IndiceDevinette, ScoreConfig


class Command(BaseCommand):
    help = 'Recalcule les scores de tous les utilisateurs en fonction de leur progression'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Nom d\'utilisateur spécifique (optionnel)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recalculer les scores de tous les utilisateurs (par défaut)',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        
        # Si un username est spécifié, ne traiter que cet utilisateur
        if username:
            try:
                users = [User.objects.get(username=username)]
                self.stdout.write(f'Recalcul du score pour {username}...\n')
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Utilisateur "{username}" introuvable')
                )
                return
        else:
            users = User.objects.all()
            self.stdout.write('Recalcul des scores pour tous les utilisateurs...\n')
        score_config = ScoreConfig.get_config()
        updated_count = 0
        
        for user in users:
            if hasattr(user, 'userprofile_2025'):
                profile = user.userprofile_2025
                
                # Calculer le score des énigmes
                enigmes_resolues = max(0, profile.currentEnigma - 1) if profile.currentEnigma > 0 else 0
                score_enigmes = enigmes_resolues * score_config.points_enigme_resolue
                malus_erreurs_enigmes = profile.erreurEnigma * score_config.malus_erreur_enigme
                
                # Calculer le coût des indices d'énigmes
                cout_indices_enigmes = 0
                if profile.indices_enigme_reveles:
                    indices_ids = [int(x) for x in profile.indices_enigme_reveles.split(",") if x]
                    for indice_id in indices_ids:
                        try:
                            indice = Indice.objects.get(id=indice_id)
                            cout_indices_enigmes += indice.cout
                        except Indice.DoesNotExist:
                            pass
                
                # Calculer le score des devinettes
                devinettes_resolues = max(0, profile.currentDevinette - 1) if profile.currentDevinette > 0 else 0
                score_devinettes = devinettes_resolues * score_config.points_devinette_resolue
                malus_erreurs_devinettes = profile.erreurDevinette * score_config.malus_erreur_devinette
                
                # Calculer le coût des indices de devinettes
                cout_indices_devinettes = 0
                if profile.indices_devinette_reveles:
                    indices_ids = [int(x) for x in profile.indices_devinette_reveles.split(",") if x]
                    for indice_id in indices_ids:
                        try:
                            indice = IndiceDevinette.objects.get(id=indice_id)
                            cout_indices_devinettes += indice.cout
                        except IndiceDevinette.DoesNotExist:
                            pass
                
                # Score total
                old_score = profile.score
                total_score = (
                    score_enigmes +
                    score_devinettes -
                    malus_erreurs_enigmes -
                    malus_erreurs_devinettes -
                    cout_indices_enigmes -
                    cout_indices_devinettes
                )
                
                profile.score = max(0, total_score)
                profile.save()
                
                updated_count += 1
                
                if old_score != profile.score:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ {user.username}: {old_score} → {profile.score} points'
                        )
                    )
                else:
                    self.stdout.write(
                        f'   {user.username}: {profile.score} points (inchangé)'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Scores recalculés pour {updated_count} utilisateurs !'
            )
        )
