"""
Commande de gestion pour configurer les scores du calendrier de l'avent
"""
from django.core.management.base import BaseCommand
from avent2025.models import ScoreConfig


class Command(BaseCommand):
    help = 'Afficher ou modifier la configuration des scores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show',
            action='store_true',
            help='Afficher la configuration actuelle'
        )
        parser.add_argument(
            '--enigme',
            type=int,
            help='Points par énigme résolue'
        )
        parser.add_argument(
            '--devinette',
            type=int,
            help='Points par devinette résolue'
        )
        parser.add_argument(
            '--malus-enigme',
            type=int,
            help='Malus par erreur d\'énigme'
        )
        parser.add_argument(
            '--malus-devinette',
            type=int,
            help='Malus par erreur de devinette'
        )

    def handle(self, *args, **options):
        config = ScoreConfig.get_config()
        
        # Si aucune option, afficher l'aide
        if not any([options['show'], options['enigme'], options['devinette'], 
                    options['malus_enigme'], options['malus_devinette']]):
            self.stdout.write(self.style.WARNING('Utilisez --show pour afficher la configuration'))
            self.stdout.write(self.style.WARNING('ou --enigme, --devinette, --malus-enigme, --malus-devinette pour modifier'))
            return
        
        # Modifier si des valeurs sont fournies
        modified = False
        if options['enigme'] is not None:
            config.points_enigme_resolue = options['enigme']
            modified = True
            self.stdout.write(self.style.SUCCESS(f'✓ Points par énigme: {options["enigme"]}'))
        
        if options['devinette'] is not None:
            config.points_devinette_resolue = options['devinette']
            modified = True
            self.stdout.write(self.style.SUCCESS(f'✓ Points par devinette: {options["devinette"]}'))
        
        if options['malus_enigme'] is not None:
            config.malus_erreur_enigme = options['malus_enigme']
            modified = True
            self.stdout.write(self.style.SUCCESS(f'✓ Malus erreur énigme: {options["malus_enigme"]}'))
        
        if options['malus_devinette'] is not None:
            config.malus_erreur_devinette = options['malus_devinette']
            modified = True
            self.stdout.write(self.style.SUCCESS(f'✓ Malus erreur devinette: {options["malus_devinette"]}'))
        
        if modified:
            config.save()
            self.stdout.write(self.style.SUCCESS('\n✅ Configuration sauvegardée avec succès'))
        
        # Afficher la configuration
        if options['show'] or modified:
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.HTTP_INFO('📊 CONFIGURATION DES SCORES'))
            self.stdout.write('='*50)
            self.stdout.write(f'\n🎯 Points par énigme résolue:      {config.points_enigme_resolue}')
            self.stdout.write(f'🎭 Points par devinette résolue:   {config.points_devinette_resolue}')
            self.stdout.write(f'❌ Malus par erreur d\'énigme:      -{config.malus_erreur_enigme}')
            self.stdout.write(f'❌ Malus par erreur de devinette:  -{config.malus_erreur_devinette}')
            self.stdout.write('\n' + '='*50)
            
            # Afficher un exemple de calcul
            self.stdout.write(f'\n💡 Exemple de calcul:')
            self.stdout.write(f'   3 énigmes + 5 devinettes + 2 erreurs énigmes + 3 erreurs devinettes =')
            exemple_score = (
                3 * config.points_enigme_resolue +
                5 * config.points_devinette_resolue -
                2 * config.malus_erreur_enigme -
                3 * config.malus_erreur_devinette
            )
            self.stdout.write(self.style.SUCCESS(f'   Score = {exemple_score} points'))
            self.stdout.write('='*50 + '\n')
