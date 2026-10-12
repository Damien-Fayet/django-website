from django.core.management.base import BaseCommand

from avent2026.models import Hint, Puzzle

# Contenu de test, à remplacer par le vrai contenu (via l'admin) une fois le thème choisi.
SAMPLES = [
    dict(kind="enigme", day=1, title="Le compte est bon", story="<p>La fenêtre de la ferme s'allume : un vieux fermier compte ses sacs de grain à la lueur d'une bougie, 2, 4, 8, 16, 32… Il sourit : il y en aura assez pour le festin.</p>",
         text="<p>Je suis le prochain nombre : 2, 4, 8, 16, …</p>", answers="32\ntrente deux",
         hints=["Chaque nombre est le double du précédent.", "16 × 2 = ?"]),
    dict(kind="devinette", day=1, title="Qui suis-je ?", story="<p>Une lanterne grésille au bout du chemin. Sous sa lueur, un enfant se dresse sur la pointe des pieds : « Il est passé par là, j'ai vu du rouge et du blanc ! »</p>",
         text="<p>Je suis rouge et blanc, j'apporte des cadeaux et je n'aime pas la cheminée trop étroite.</p>",
         answers="le père noël\npere noel\nle pere noel", hints=["Il a une grande barbe blanche."]),
    dict(kind="enigme", day=2, title="Dans le sapin", story="<p>La vitrine du magasin se rallume : une guirlande clignote derrière la vitre, et une souris en profite pour grignoter un bout de pain d'épices.</p>",
         text="<p>J'ai des branches mais pas de feuilles, je brille sans soleil. Que suis-je ?</p>", answers="guirlande\nune guirlande",
         hints=["On m'accroche au sapin."]),
    dict(kind="devinette", day=2, title="Gourmandise", story="<p>La lanterne devant la pâtisserie s'allume, et l'odeur de chocolat fait sortir le pâtissier en tablier, la louche à la main.</p>",
         text="<p>On me coupe en tranches, je suis roulée et je suis en chocolat à Noël.</p>",
         answers="la bûche\nbuche\nla buche\nbûche de noël", hints=["C'est un dessert."]),
]


class Command(BaseCommand):
    help = "Crée (ou met à jour) 2 jours de contenu de test (une énigme et une devinette par jour, histoires « vues par la fenêtre »)."

    def handle(self, *args, **options):
        for sample in SAMPLES:
            data = dict(sample)
            hints = data.pop("hints")
            puzzle, _ = Puzzle.objects.update_or_create(
                kind=data.pop("kind"), day=data.pop("day"), defaults=data)
            for number, text in enumerate(hints, start=1):
                Hint.objects.update_or_create(puzzle=puzzle, number=number, defaults={"text": text})
        self.stdout.write(self.style.SUCCESS(f"{len(SAMPLES)} puzzles de test prêts."))
