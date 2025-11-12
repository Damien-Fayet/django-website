from django.core.management.base import BaseCommand
from chessTrainer.models import ChessGame
from chessTrainer.views import analyze_game_with_stockfish

class Command(BaseCommand):
    help = "Réanalyse toutes les parties où l'utilisateur est noir."

    def handle(self, *args, **options):
        count = 0
        for game in ChessGame.objects.filter(analyzed=True):
            if game.username.lower() == game.black_player.lower():
                self.stdout.write(f"Réanalyse de la partie {game.game_id} ({game.username} avec les noirs)")
                game.analyzed = False
                game.save()
                analyze_game_with_stockfish(game)
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Réanalyse terminée : {count} parties réanalysées (noirs)."))
