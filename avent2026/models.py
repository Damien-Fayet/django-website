from django.conf import settings
from django.db import models


class Puzzle(models.Model):
    """Une énigme ou une devinette attachée à un jour (1-24) : une de chaque au plus par jour (deux pistes)."""

    ENIGME = "enigme"
    DEVINETTE = "devinette"
    KINDS = [(ENIGME, "Énigme"), (DEVINETTE, "Devinette")]

    kind = models.CharField(max_length=10, choices=KINDS)
    day = models.PositiveSmallIntegerField("Jour", help_text="1 à 24")
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
        help_text="Laisser vide : 1er + jour décembre 2026.",
    )

    class Meta:
        ordering = ["day", "kind"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "day"], name="uniq_avent2026_puzzle"),
            models.CheckConstraint(check=models.Q(day__gte=1, day__lte=24), name="avent2026_day_1_24"),
        ]

    def __str__(self):
        return f"J{self.day} {self.get_kind_display()} — {self.title}"


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
    first_seen_at = models.DateTimeField(
        "Premier affichage", null=True, blank=True,
        help_text="Première ouverture de la page du puzzle (vide : avant le suivi, ou réponse envoyée sans l'avoir ouverte).",
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


class Submission(models.Model):
    """Journal des réponses envoyées (texte tel que saisi), pour le suivi staff.

    Indépendant d'`Attempt` (pas de clé vers elle) : remettre une progression à zéro dans l'admin
    ne doit pas effacer la trace.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avent2026_submissions")
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="submissions")
    answer = models.CharField("Réponse saisie", max_length=200)
    correct = models.BooleanField("Correcte")
    created_at = models.DateTimeField("Envoyée le", auto_now_add=True)
    ip = models.GenericIPAddressField("Adresse IP", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "puzzle"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.puzzle} — {self.answer!r}"
