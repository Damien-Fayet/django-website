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
    cout = models.IntegerField(
        default=1,
        choices=[(1, '1 point'), (2, '2 points'), (3, '3 points')],
        verbose_name='Coût en points'
    )
    image = models.ImageField(default="", blank=True, null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    texte = models.TextField(blank=True)
    
    def __str__(self):
        return f"Indice #{self.numero} ({self.get_categorie_display()}) - {self.cout}pt : {self.enigme}"
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
    cout = models.IntegerField(
        default=1,
        choices=[(1, '1 point'), (2, '2 points'), (3, '3 points')],
        verbose_name='Coût en points'
    )
    image = models.ImageField(default="", blank=True, null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    texte = models.TextField(blank=True)
    
    def __str__(self):
        return f"Indice #{self.numero} ({self.get_categorie_display()}) - {self.cout}pt : {self.enigme}"