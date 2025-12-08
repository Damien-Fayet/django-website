from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from datetime import date
from django.core.validators import int_list_validator



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile_2025')
    currentEnigma = models.IntegerField(default=0)
    erreurEnigma = models.IntegerField(default=0)
    currentDevinette = models.IntegerField(default=0)
    erreurDevinette = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    indices_enigme_reveles = models.CharField(validators=[int_list_validator()], default="", max_length=200, blank=True)
    indices_devinette_reveles = models.CharField(validators=[int_list_validator()],default="", max_length=200, blank=True)
    is_family = models.BooleanField(default=False, verbose_name="Membre de la famille", help_text="Cochez pour marquer cet utilisateur comme membre de la famille")
    is_cheater = models.BooleanField(default=False, verbose_name="Tricheur détecté", help_text="Cochez pour marquer cet utilisateur comme tricheur (exclu des classements)")
    # Stockage des réponses validées (format JSON: {"1": "réponse1", "2": "réponse2"})
    reponses_enigmes = models.JSONField(default=dict, blank=True, verbose_name="Réponses validées des énigmes")
    reponses_devinettes = models.JSONField(default=dict, blank=True, verbose_name="Réponses validées des devinettes")
    
    def __str__(self):
        return f"{self.user} Enigme {self.currentEnigma}, Devinette {self.currentDevinette}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée automatiquement un UserProfile quand un User est créé"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Sauvegarde le UserProfile quand le User est sauvegardé"""
    if hasattr(instance, 'userprofile_2025'):
        instance.userprofile_2025.save()


def get_or_create_profile(user):
    """Fonction utilitaire pour garantir qu'un UserProfile existe"""
    if not hasattr(user, 'userprofile_2025'):
        UserProfile.objects.create(user=user)
    return user.userprofile_2025

    
class Enigme(models.Model):
    id = models.IntegerField(primary_key=True)
    titre = models.CharField(max_length=100)
    texte = models.TextField()
    image_name = models.ImageField(default="",blank=True,null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    reponse = models.CharField(max_length=100)
    date_dispo = models.DateField(default="2025-11-02")
    def __str__(self):
        return f"Enigme {self.id} : {self.titre}"
    @property
    def is_dispo(self):
        return date.today() >= self.date_dispo

class Indice(models.Model):
    MECANIQUE = 'ME'
    REPONSE = 'RE'
    CATEGORIES = [
        (MECANIQUE, 'Mécanique'),
        (REPONSE, 'Réponse attendue'),
    ]
    
    NORMAL = 'NO'
    LAST_CHANCE = 'LC'
    TYPE_INDICE = [
        (NORMAL, 'Normal'),
        (LAST_CHANCE, 'Last Chance'),
    ]
    
    enigme = models.ForeignKey(
        'Enigme',
        on_delete=models.CASCADE,
    )
    numero = models.IntegerField(default=1)
    categorie = models.CharField(
        max_length=2,
        choices=CATEGORIES,
        default=MECANIQUE,
        verbose_name='Catégorie'
    )
    type_indice = models.CharField(
        max_length=2,
        choices=TYPE_INDICE,
        default=NORMAL,
        verbose_name='Type d\'indice',
        help_text='Normal: disponible immédiatement | Last Chance: débloqué à l\'énigme suivante'
    )
    cout = models.IntegerField(
        default=1,
        choices=[(1, '1 point'), (2, '2 points'), (3, '3 points'), (5, '5 points'), (8, '8 points'), (10, '10 points')],
        verbose_name='Coût en points'
    )
    image = models.ImageField(default="", blank=True, null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    texte = models.TextField(blank=True)
    
    def __str__(self):
        type_str = " [LAST CHANCE]" if self.type_indice == self.LAST_CHANCE else ""
        return f"Indice #{self.numero} ({self.get_categorie_display()}) - {self.cout}pt{type_str} : {self.enigme}"
    
    class Meta:
        ordering = ['enigme', 'numero']


class ScoreConfig(models.Model):
    """Configuration des points et malus pour le système de score"""
    
    # Points positifs
    points_enigme_resolue = models.IntegerField(
        default=100,
        verbose_name="Points par énigme résolue",
        help_text="Nombre de points gagnés pour chaque énigme résolue"
    )
    points_devinette_resolue = models.IntegerField(
        default=10,
        verbose_name="Points par devinette résolue",
        help_text="Nombre de points gagnés pour chaque devinette résolue"
    )
    
    # Malus
    malus_erreur_enigme = models.IntegerField(
        default=10,
        verbose_name="Malus par erreur d'énigme",
        help_text="Nombre de points perdus pour chaque mauvaise réponse à une énigme"
    )
    malus_erreur_devinette = models.IntegerField(
        default=2,
        verbose_name="Malus par erreur de devinette",
        help_text="Nombre de points perdus pour chaque mauvaise réponse à une devinette"
    )
    
    # Singleton pattern - une seule configuration
    class Meta:
        verbose_name = "Configuration des scores"
        verbose_name_plural = "Configuration des scores"
    
    def __str__(self):
        return "Configuration des scores"
    
    def save(self, *args, **kwargs):
        """Assurer qu'il n'y a qu'une seule instance de configuration"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Récupérer la configuration (créer si n'existe pas)"""
        config, created = cls.objects.get_or_create(pk=1)
        return config
class Devinette(models.Model):
    FILM = 'FI'
    CHANSON = 'CH'
    PERSONALITE = 'PE'
    GENRES = [
        (FILM, 'Film'),
        (CHANSON, 'Chanson'),
        (PERSONALITE, 'Personalité'),
    ]
    id = models.IntegerField(primary_key=True)
    titre = models.CharField(max_length=100)
    texte = models.TextField(blank=True)
    image_name = models.ImageField(default="", blank=True, null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    reponse = models.CharField(max_length=100)
    date_dispo = models.DateField(default="2025-11-02")
    genre = models.CharField(max_length=100,
        choices=GENRES,
        default=FILM,)
    def __str__(self):
        return f"Devinette {self.id} : {self.titre}"
    @property
    def is_dispo(self):
        return date.today() >= self.date_dispo
    
class IndiceDevinette(models.Model):
    MECANIQUE = 'ME'
    REPONSE = 'RE'
    CATEGORIES = [
        (MECANIQUE, 'Mécanique'),
        (REPONSE, 'Réponse attendue'),
    ]
    
    NORMAL = 'NO'
    LAST_CHANCE = 'LC'
    TYPE_INDICE = [
        (NORMAL, 'Normal'),
        (LAST_CHANCE, 'Last Chance'),
    ]
    
    # Note: Le champ s'appelle 'enigme' mais référence Devinette (hérité de avent2024)
    enigme = models.ForeignKey(
        'Devinette',
        on_delete=models.CASCADE,
    )
    numero = models.IntegerField(default=1)
    categorie = models.CharField(
        max_length=2,
        choices=CATEGORIES,
        default=MECANIQUE,
        verbose_name='Catégorie'
    )
    type_indice = models.CharField(
        max_length=2,
        choices=TYPE_INDICE,
        default=NORMAL,
        verbose_name='Type d\'indice',
        help_text='Normal: disponible immédiatement | Last Chance: débloqué à la devinette suivante'
    )
    cout = models.IntegerField(
        default=1,
        choices=[(1, '1 point'), (2, '2 points'), (3, '3 points'), (5, '5 points'), (8, '8 points'), (10, '10 points')],
        verbose_name='Coût en points'
    )
    image = models.ImageField(default="", blank=True, null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    texte = models.TextField(blank=True)
    
    def __str__(self):
        type_str = " [LAST CHANCE]" if self.type_indice == self.LAST_CHANCE else ""
        return f"Indice #{self.numero} ({self.get_categorie_display()}) - {self.cout}pt{type_str} : {self.enigme}"
    
    class Meta:
        ordering = ['enigme', 'numero']

class AuditLog(models.Model):
    """Modèle pour tracker les activités des utilisateurs"""
    
    # Types d'actions
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    ENIGME_VIEW = 'ENIGME_VIEW'
    ENIGME_SUBMIT_SUCCESS = 'ENIGME_SUCCESS'
    ENIGME_SUBMIT_FAIL = 'ENIGME_FAIL'
    DEVINETTE_VIEW = 'DEVINETTE_VIEW'
    DEVINETTE_SUBMIT_SUCCESS = 'DEVINETTE_SUCCESS'
    DEVINETTE_SUBMIT_FAIL = 'DEVINETTE_FAIL'
    INDICE_REVEAL = 'INDICE_REVEAL'
    INDICE_DEVINETTE_REVEAL = 'INDICE_DEV_REVEAL'
    CLASSEMENT_VIEW = 'CLASSEMENT_VIEW'
    HOME_VIEW = 'HOME_VIEW'
    
    ACTION_CHOICES = [
        (LOGIN, 'Connexion'),
        (LOGOUT, 'Déconnexion'),
        (ENIGME_VIEW, 'Consultation énigme'),
        (ENIGME_SUBMIT_SUCCESS, 'Énigme réussie'),
        (ENIGME_SUBMIT_FAIL, 'Énigme échouée'),
        (DEVINETTE_VIEW, 'Consultation devinette'),
        (DEVINETTE_SUBMIT_SUCCESS, 'Devinette réussie'),
        (DEVINETTE_SUBMIT_FAIL, 'Devinette échouée'),
        (INDICE_REVEAL, 'Révélation indice énigme'),
        (INDICE_DEVINETTE_REVEAL, 'Révélation indice devinette'),
        (CLASSEMENT_VIEW, 'Consultation classement'),
        (HOME_VIEW, 'Consultation accueil'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Détails spécifiques à l'action
    enigme_id = models.IntegerField(null=True, blank=True, verbose_name="ID Énigme")
    devinette_id = models.IntegerField(null=True, blank=True, verbose_name="ID Devinette")
    indice_id = models.IntegerField(null=True, blank=True, verbose_name="ID Indice")
    reponse_donnee = models.CharField(max_length=500, blank=True, verbose_name="Réponse donnée")
    details = models.TextField(blank=True, verbose_name="Détails additionnels")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Log d'audit"
        verbose_name_plural = "Logs d'audit"
    
    def __str__(self):
        action_display = self.get_action_display()
        if self.enigme_id:
            return f"{self.user.username} - {action_display} (Énigme #{self.enigme_id}) - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"
        elif self.devinette_id:
            return f"{self.user.username} - {action_display} (Devinette #{self.devinette_id}) - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"
        else:
            return f"{self.user.username} - {action_display} - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"
