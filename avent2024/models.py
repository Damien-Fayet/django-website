from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from datetime import date
from django.core.validators import int_list_validator



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    currentEnigma = models.IntegerField(default=0)
    erreurEnigma = models.IntegerField(default=0)
    currentDevinette = models.IntegerField(default=0)
    erreurDevinette = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    indices_enigme_reveles = models.CharField(validators=[int_list_validator()], default="", max_length=200, blank=True)
    indices_devinette_reveles = models.CharField(validators=[int_list_validator()],default="", max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.user} Enigme {self.currentEnigma}, Devinette {self.currentDevinette}"
    
class Enigme(models.Model):
    id = models.IntegerField(primary_key=True)
    titre = models.CharField(max_length=100)
    texte = models.TextField()
    image_name = models.ImageField(default="",blank=True,null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    reponse = models.CharField(max_length=100)
    date_dispo = models.DateField(default="2024-11-02")
    def __str__(self):
        return f"Enigme {self.id} : {self.titre}"
    @property
    def is_dispo(self):
        return date.today() > self.date_dispo

class Indice(models.Model):
    enigme = models.ForeignKey(
        'Enigme',
        on_delete=models.CASCADE,
    )
    numero = models.IntegerField(default=1)
    image = models.ImageField(default="", blank=True, null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    texte = models.TextField(blank=True)
    def __str__(self):
        return f"Indice {self.id} : Enigme {self.enigme}, numero : {self.numero}"
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
    date_dispo = models.DateField(default="2024-11-02")
    genre = models.CharField(max_length=100,
        choices=GENRES,
        default=FILM,)
    def __str__(self):
        return f"Devinette {self.id} : {self.titre}"
    @property
    def is_dispo(self):
        return date.today() > self.date_dispo
    
class IndiceDevinette(models.Model):    
    enigme = models.ForeignKey(
        'Devinette',
        on_delete=models.CASCADE,
    )
    numero = models.IntegerField(default=1)
    image = models.ImageField(default="", null=True, upload_to="uploads", height_field=None, width_field=None, max_length=None)
    texte = models.TextField()    
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()