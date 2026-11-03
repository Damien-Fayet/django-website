from django.conf import settings
from django.db import models


class LoginEvent(models.Model):
    """Une connexion (formulaire de connexion, inscription ou admin) : journal pour le suivi staff.

    Vit dans `accounts` et non dans une app d'édition : les éditions annuelles sont supprimées,
    l'historique des connexions doit leur survivre.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_events")
    at = models.DateTimeField("Connexion", auto_now_add=True)
    ip = models.GenericIPAddressField("Adresse IP", null=True, blank=True)

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [models.Index(fields=["at"])]

    def __str__(self):
        return f"{self.user} — {self.at:%d/%m/%Y %H:%M:%S}"


class Profile(models.Model):
    """Réglages d'un compte qui survivent aux éditions annuelles (comme `LoginEvent`, d'où `accounts`).

    `is_family` : membre de la famille. Seuls ces joueurs voient (et figurent dans) le classement « Famille » du
    jeu. Cochée à la main dans l'admin (Utilisateurs, section « Profil »). Le profil est créé à la demande : un
    compte sans ligne n'est pas de la famille.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    is_family = models.BooleanField(
        "Membre de la famille", default=False,
        help_text="Donne accès au classement Famille, réservé à ces joueurs.")

    class Meta:
        verbose_name = "profil"

    def __str__(self):
        return f"Profil de {self.user}"
