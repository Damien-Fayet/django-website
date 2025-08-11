from django.db import models
from django.urls import reverse
from datetime import date

class Book(models.Model):
    # Informations de base
    isbn = models.CharField(max_length=13, unique=True, help_text="Code ISBN du livre")
    title = models.CharField(max_length=200, verbose_name="Titre")
    authors = models.CharField(max_length=300, verbose_name="Auteur(s)")
    publisher = models.CharField(max_length=200, blank=True, verbose_name="Éditeur")
    published_date = models.DateField(blank=True, null=True, verbose_name="Date de publication")
    description = models.TextField(blank=True, verbose_name="Description")
    page_count = models.IntegerField(blank=True, null=True, verbose_name="Nombre de pages")
    
    # Informations pédagogiques
    age_range = models.CharField(max_length=50, blank=True, verbose_name="Tranche d'âge")
    reading_level = models.CharField(max_length=50, blank=True, verbose_name="Niveau de lecture")
    themes = models.CharField(max_length=200, blank=True, verbose_name="Thème(s)", help_text="Séparez les thèmes par des virgules (ex: aventure, amitié, nature)")
    
    # Gestion de la bibliothèque
    comments = models.TextField(blank=True, verbose_name="Commentaires de la maîtresse")
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)], blank=True, null=True, verbose_name="Note (1-5)")
    
    # Métadonnées
    cover_image_url = models.URLField(blank=True, verbose_name="URL de la couverture")
    google_books_id = models.CharField(max_length=100, blank=True, verbose_name="ID Google Books")
    added_date = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")
    updated_date = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")
    
    class Meta:
        verbose_name = "Livre"
        verbose_name_plural = "Livres"
        ordering = ['title']
    
    def __str__(self):
        return f"{self.title} - {self.authors}"
    
    def get_absolute_url(self):
        return reverse('biblio:book_detail', kwargs={'pk': self.pk})
