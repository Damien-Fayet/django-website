import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from . import village

# Médias d'un énoncé : extensions acceptées (les navigateurs lisent mp4 et webm ; un .mov d'iPhone est à convertir)
# et poids maximal. Les vidéos servies par Django (Pi 3) : 200 Mo au plus, et la limite de Cloudflare (100 Mo par
# envoi sur l'offre gratuite) s'applique à l'envoi par l'admin du site public.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
VIDEO_EXTENSIONS = (".mp4", ".webm")
IMAGE_MAX_BYTES = 2 * 1024 * 1024
VIDEO_MAX_BYTES = 200 * 1024 * 1024


def validate_media(f):
    """Refuse un média d'une autre sorte que image/vidéo, ou trop lourd (vérifié à l'envoi seulement)."""
    ext = os.path.splitext(f.name)[1].lower()
    allowed = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
    if ext not in allowed:
        raise ValidationError(f"Format non accepté ({ext or 'sans extension'}). Formats : {', '.join(allowed)}.")
    if getattr(f, "_committed", False):  # FieldFile déjà enregistré : rien à revérifier (et pas de lecture disque)
        return
    limit, label = (VIDEO_MAX_BYTES, "200 Mo") if ext in VIDEO_EXTENSIONS else (IMAGE_MAX_BYTES, "2 Mo")
    if f.size > limit:
        raise ValidationError(f"Fichier trop lourd ({f.size / 1024 / 1024:.1f} Mo) : {label} au plus.")


class Puzzle(models.Model):
    """Une énigme ou une devinette attachée à un jour (1-24) : une de chaque au plus par jour (deux pistes)."""

    ENIGME = "enigme"
    DEVINETTE = "devinette"
    KINDS = [(ENIGME, "Énigme"), (DEVINETTE, "Devinette")]

    kind = models.CharField(max_length=10, choices=KINDS)
    day = models.PositiveSmallIntegerField(
        "Jour", help_text="Jour du mois, de 1 à 24. Énigmes : 1, 2, 5, 9, 12, 16, 19 ou 23 (un verrou chacune).")
    title = models.CharField("Titre", max_length=120)
    text = models.TextField(
        "Énoncé", blank=True,
        help_text="Facultatif si un média est joint. HTML autorisé (contenu saisi par l'admin uniquement).")
    image = models.FileField(
        "Image ou vidéo", upload_to="avent2026/", blank=True, validators=[validate_media],
        help_text="Facultatif. Image (jpg, png, webp, gif ; 2 Mo au plus, idéalement < 200 Ko) ou vidéo "
                  "(mp4 ou webm ; 200 Mo au plus, mais l'espace disque est limité : la compresser).",
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

    @property
    def is_video(self):
        """Vrai si le média joint est une vidéo (sinon, c'est une image ou rien)."""
        return bool(self.image) and os.path.splitext(self.image.name)[1].lower() in VIDEO_EXTENSIONS

    def clean(self):
        """Les énigmes ne se publient que les jours de la cellule ; un puzzle a un énoncé, un média, ou les deux."""
        if self.kind == self.ENIGME and self.day not in village.ENIGME_DAYS:
            days = ", ".join(str(d) for d in village.ENIGME_DAYS)
            raise ValidationError({"day": f"Les énigmes sortent les jours suivants : {days}."})
        if not self.text.strip() and not self.image:
            raise ValidationError({"text": "Ajoutez un énoncé ou une image/vidéo : la page serait vide."})


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


class LeaderboardDay(models.Model):
    """Nombre de visites de la page du classement par joueur et par jour (heure de Paris), pour le haut-fait
    « Fana du classement ». Un compteur par jour plutôt qu'une ligne par visite : la table reste minuscule."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avent2026_board_days")
    day = models.DateField("Jour")
    views = models.PositiveIntegerField("Visites", default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "day"], name="uniq_avent2026_board_day"),
        ]

    def __str__(self):
        return f"{self.user} — {self.day} : {self.views}"
