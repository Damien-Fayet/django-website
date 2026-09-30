from django.core.management.base import BaseCommand

from avent2026.models import Hint, Puzzle

# Contenu de test, à remplacer par le vrai contenu (via l'admin) une fois le thème choisi.
SAMPLES = [
    dict(kind="enigme", day=1, difficulty="facile", title="Le compte est bon",
         text="<p>Je suis le prochain nombre : 2, 4, 8, 16, …</p>", answers="32\ntrente deux",
         hints=["Chaque nombre est le double du précédent.", "16 × 2 = ?"]),
    dict(kind="enigme", day=1, difficulty="difficile", title="Suite piégeuse",
         text="<p>1, 1, 2, 3, 5, 8, 13, … Quel est le nombre suivant <b>après</b> 21 ?</p>", answers="34\ntrente quatre",
         hints=["Regarde comment chaque nombre se forme à partir des deux précédents.", "13 + 21 = 34… mais attends, que demande-t-on ?"]),
    dict(kind="devinette", day=1, difficulty="facile", title="Qui suis-je ?",
         text="<p>Je suis rouge et blanc, j'apporte des cadeaux et je n'aime pas la cheminée trop étroite.</p>",
         answers="le père noël\npere noel\nle pere noel", hints=["Il a une grande barbe blanche."]),
    dict(kind="enigme", day=2, difficulty="facile", title="Dans le sapin",
         text="<p>J'ai des branches mais pas de feuilles, je brille sans soleil. Que suis-je ?</p>", answers="guirlande\nune guirlande",
         hints=["On m'accroche au sapin."]),
    dict(kind="enigme", day=2, difficulty="difficile", title="Le mot caché",
         text="<p>Je commence la nuit et je finis le jour, mais je ne suis ni l'un ni l'autre. Quelle est ma lettre ?</p>", answers="n\nla lettre n\nlettre n",
         hints=["Regarde le début et la fin des mots « nuit » et « jour »."]),
    dict(kind="devinette", day=2, difficulty="facile", title="Gourmandise",
         text="<p>On me coupe en tranches, je suis roulée et je suis en chocolat à Noël.</p>",
         answers="la bûche\nbuche\nla buche\nbûche de noël", hints=["C'est un dessert."]),
]


class Command(BaseCommand):
    help = "Crée (ou met à jour) 2 jours de contenu de test pour avent2026."

    def handle(self, *args, **options):
        for sample in SAMPLES:
            data = dict(sample)
            hints = data.pop("hints")
            puzzle, _ = Puzzle.objects.update_or_create(
                kind=data.pop("kind"), day=data.pop("day"), difficulty=data.pop("difficulty"), defaults=data)
            for number, text in enumerate(hints, start=1):
                Hint.objects.update_or_create(puzzle=puzzle, number=number, defaults={"text": text})
        self.stdout.write(self.style.SUCCESS(f"{len(SAMPLES)} puzzles de test prêts."))
