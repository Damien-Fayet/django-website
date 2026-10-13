from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from . import village


class Puzzle(models.Model):
    """Une énigme ou une devinette attachée à un jour (1-24) : une de chaque au plus par jour (deux pistes)."""

    ENIGME = "enigme"
    DEVINETTE = "devinette"
    KINDS = [(ENIGME, "Énigme"), (DEVINETTE, "Devinette")]

    kind = models.CharField(max_length=10, choices=KINDS)
    day = models.PositiveSmallIntegerField(
        "Jour", help_text="Jour du mois, de 1 à 24. Énigmes : 1, 2, 5, 9, 12, 16, 19 ou 23 (un verrou chacune).")
    title = models.CharField("Titre", max_length=120)
    text = models.TextField("Énoncé", help_text="HTML autorisé (contenu saisi par l'admin uniquement).")
    image = models.FileField(
        "Image", upload_to="avent2026/", blank=True,
        help_text="Optionnel. Garder < 200 Ko (espace disque limité).",
    )
    answers = models.TextField(
        "Réponses acceptées",
        help_text="Une par ligne. Comparaison sans accents, majuscules ni ponctuation.",
    )
    story = models.TextField(
        "Fragment d'histoire", blank=True,
        help_text="Révélé au joueur quand il résout ce puzzle (HTML autorisé).",
    )
    base_points = models.PositiveIntegerField(
        "Points de base", null=True, blank=True,
        help_text="Laisser vide pour utiliser la valeur par défaut (voir scoring.py).",
    )
    unlock_date = models.DateField(
        "Date de déblocage", null=True, blank=True,
        help_text="Laisser vide : le jour de décembre 2026 (à 6 h pour les énigmes, à minuit pour les devinettes).",
    )

    class Meta:
        ordering = ["day", "kind"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "day"], name="uniq_avent2026_puzzle"),
            models.CheckConstraint(check=models.Q(day__gte=1, day__lte=24), name="avent2026_day_1_24"),
        ]

    def __str__(self):
        return f"J{self.day} {self.get_kind_display()} — {self.title}"

    def clean(self):
        """Les énigmes ne se publient que les jours de la cellule (mardi 1er, mercredis et samedis)."""
        if self.kind == self.ENIGME and self.day not in village.ENIGME_DAYS:
            days = ", ".join(str(d) for d in village.ENIGME_DAYS)
            raise ValidationError({"day": f"Les énigmes sortent les jours suivants : {days}."})


class Hint(models.Model):
    """Indice progressif : numéro croissant, coût en points."""

    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="hints")
    number = models.PositiveSmallIntegerField("Numéro", default=1)
    text = models.TextField("Indice")
    cost = models.PositiveIntegerField("Coût (points)", null=True, blank=True,
                                       help_text="Laisser vide pour la valeur par défaut.")

    class Meta:
        ordering = ["puzzle", "number"]
        constraints = [
            models.UniqueConstraint(fields=["puzzle", "number"], name="uniq_avent2026_hint"),
        ]

    def __str__(self):
        return f"{self.puzzle} — indice {self.number}"


class Attempt(models.Model):
    """Progression d'un joueur sur un puzzle (une ligne par joueur et puzzle)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avent2026_attempts")
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="attempts")
    errors = models.PositiveIntegerField(default=0)
    solved_at = models.DateTimeField(null=True, blank=True)
    points = models.IntegerField("Points obtenus", default=0)
    rank = models.PositiveSmallIntegerField(
        "Place à la résolution", null=True, blank=True,
        help_text="Rang parmi les joueurs (hors staff) qui ont résolu ce puzzle ; sert au bonus de podium.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "puzzle"], name="uniq_avent2026_attempt"),
        ]
        indexes = [models.Index(fields=["puzzle", "solved_at"])]

    @property
    def solved(self):
        return self.solved_at is not None


class HintReveal(models.Model):
    """Indice révélé par un joueur (le coût est appliqué à la résolution)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avent2026_hints")
    hint = models.ForeignKey(Hint, on_delete=models.CASCADE, related_name="reveals")
    revealed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "hint"], name="uniq_avent2026_reveal"),
        ]
