from django.core.management.base import BaseCommand

from avent2026.models import Hint, Puzzle

# Contenu de test, à remplacer par le vrai contenu (via l'admin) une fois le thème choisi.
SAMPLES = [
    dict(kind="enigme", day=1, title="Le compte est bon", story="<p>Le robot aligne ses engrenages : 2, 4, 8, 16, 32… Son processeur ronronne. Il sait enfin compter.</p>",
         text="<p>Je suis le prochain nombre : 2, 4, 8, 16, …</p>", answers="32\ntrente deux",
         hints=["Chaque nombre est le double du précédent.", "16 × 2 = ?"]),
    dict(kind="devinette", day=1, title="Qui suis-je ?", story="<p>Un écho dans son antenne encore muette : « …rouge et blanc… » Le robot comprend qui l'appelle.</p>",
         text="<p>Je suis rouge et blanc, j'apporte des cadeaux et je n'aime pas la cheminée trop étroite.</p>",
         answers="le père noël\npere noel\nle pere noel", hints=["Il a une grande barbe blanche."]),
    dict(kind="enigme", day=2, title="Dans le sapin", story="<p>Une guirlande clignote dans l'atelier. Le robot y branche son câble : il a de l'énergie pour la journée.</p>",
         text="<p>J'ai des branches mais pas de feuilles, je brille sans soleil. Que suis-je ?</p>", answers="guirlande\nune guirlande",
         hints=["On m'accroche au sapin."]),
    dict(kind="devinette", day=2, title="Gourmandise", story="<p>Une odeur de chocolat flotte dans l'atelier. Le robot n'a pas de nez, mais il sent que le chalet est proche.</p>",
         text="<p>On me coupe en tranches, je suis roulée et je suis en chocolat à Noël.</p>",
         answers="la bûche\nbuche\nla buche\nbûche de noël", hints=["C'est un dessert."]),
]


class Command(BaseCommand):
    help = "Crée (ou met à jour) 2 jours de contenu de test (une énigme et une devinette par jour)."

    def handle(self, *args, **options):
        for sample in SAMPLES:
            data = dict(sample)
            hints = data.pop("hints")
            puzzle, _ = Puzzle.objects.update_or_create(
                kind=data.pop("kind"), day=data.pop("day"), defaults=data)
            for number, text in enumerate(hints, start=1):
                Hint.objects.update_or_create(puzzle=puzzle, number=number, defaults={"text": text})
        self.stdout.write(self.style.SUCCESS(f"{len(SAMPLES)} puzzles de test prêts."))
