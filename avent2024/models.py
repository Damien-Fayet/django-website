from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from datetime import date



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    currentEnigma = models.IntegerField(default=0)
    def __str__(self):
        return f"{self.user} Enigme {self.currentEnigma}"
    
class Enigme(models.Model):
    id = models.IntegerField(primary_key=True)
    titre = models.CharField(max_length=100)
    texte = models.TextField()
    image_name = models.ImageField(default="", upload_to="uploads", height_field=None, width_field=None, max_length=None)
    reponse = models.CharField(max_length=100)
    date_dispo = models.DateField(default="2024-11-02")
    def __str__(self):
        return f"Enigme {self.id} : {self.titre}"
    @property
    def is_dispo(self):
        return date.today() > self.date_dispo
        
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()