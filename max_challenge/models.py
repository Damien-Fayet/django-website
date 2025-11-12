from django.db import models
from PIL import Image

class Photo(models.Model):
    """Photo à deviner découpée en grille 10x10"""
    name = models.CharField(max_length=200, verbose_name="Nom de la personne")
    image = models.ImageField(upload_to='max_challenge/photos/', verbose_name="Photo")
    image_400x400 = models.ImageField(upload_to='max_challenge/photos_400/', blank=True, verbose_name="Image redimensionnée")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Photo"
        verbose_name_plural = "Photos"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image and not self.image_400x400:
            self.resize_to_400x400()
    
    def resize_to_400x400(self):
        """Redimensionne l'image en 400x600 pixels (ratio 2:3 pour images portrait)"""
        try:
            from django.core.files.base import ContentFile
            from io import BytesIO
            
            # Ouvrir l'image
            img = Image.open(self.image.path)
            
            # Convertir en RGB si nécessaire
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Détecter si l'image est portrait (hauteur > largeur) ou paysage
            width, height = img.size
            is_portrait = height > width
            
            if is_portrait:
                # Image portrait : redimensionner en 400x600 (ratio 2:3)
                target_width, target_height = 400, 600
                # Calculer le ratio pour crop
                target_ratio = 2 / 3  # largeur / hauteur
                current_ratio = width / height
                
                if current_ratio > target_ratio:
                    # Image trop large, crop sur la largeur
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, height))
                else:
                    # Image trop haute, crop sur la hauteur
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    img = img.crop((0, top, width, top + new_height))
            else:
                # Image paysage ou carrée : crop en carré 400x400
                target_width, target_height = 400, 400
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                img = img.crop((left, top, left + size, top + size))
            
            # Redimensionner à la taille cible
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Sauvegarder dans un buffer avec compression modérée
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)
            
            # Sauvegarder dans le champ image_400x400
            filename = f"{self.name}_{target_width}x{target_height}.jpg"
            self.image_400x400.save(filename, ContentFile(buffer.read()), save=False)
            self.save(update_fields=['image_400x400'])
            
            print(f"✅ Image {target_width}x{target_height} générée pour {self.name}")
        except Exception as e:
            print(f"❌ Erreur lors du redimensionnement: {e}")

class Definition(models.Model):
    """Définition d'un mot à deviner"""
    word = models.CharField(max_length=100, verbose_name="Mot à deviner")
    definition = models.TextField(verbose_name="Définition")
    difficulty = models.IntegerField(
        choices=[(1, 'Facile'), (2, 'Moyen'), (3, 'Difficile')],
        default=2,
        verbose_name="Difficulté"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Définition"
        verbose_name_plural = "Définitions"
    
    def __str__(self):
        return f"{self.word} - {self.definition[:50]}..."

class GameSession(models.Model):
    """Session de jeu en cours"""
    name = models.CharField(max_length=100, verbose_name="Nom de la partie")
    description = models.TextField(blank=True, verbose_name="Description")
    team_a_name = models.CharField(max_length=100, default="Équipe A", verbose_name="Nom équipe A")
    team_b_name = models.CharField(max_length=100, default="Équipe B", verbose_name="Nom équipe B")
    
    # Configuration de la partie
    max_teams = models.IntegerField(default=4, verbose_name="Nombre maximum d'équipes")
    points_per_correct = models.IntegerField(default=10, verbose_name="Points par bonne réponse")
    squares_per_reveal = models.IntegerField(default=6, verbose_name="Nombre de carrés révélés par tour")
    ascii_reveal_speed = models.CharField(max_length=10, default='medium', choices=[
        ('slow', 'Lente'),
        ('medium', 'Moyenne'),
        ('fast', 'Rapide'),
    ], verbose_name="Vitesse révélation ASCII")
    definition_reveal_speed = models.CharField(max_length=10, default='medium', choices=[
        ('slow', 'Lente'),
        ('medium', 'Moyenne'),
        ('fast', 'Rapide'),
    ], verbose_name="Vitesse révélation définitions")
    
    # Photos assignées aux équipes
    team_a_photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='games_team_a', verbose_name="Photo équipe A")
    team_b_photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='games_team_b', verbose_name="Photo équipe B")
    
    # Photos pour l'image globale
    global_photos = models.ManyToManyField(Photo, related_name='global_games', verbose_name="Photos pour l'image globale")
    
    # Scores
    team_a_score = models.IntegerField(default=0, verbose_name="Score équipe A")
    team_b_score = models.IntegerField(default=0, verbose_name="Score équipe B")
    
    # État du jeu - Grille 10x10 (100 carrés numérotés de 0 à 99)
    team_a_revealed_squares = models.JSONField(default=list, verbose_name="Carrés révélés équipe A (0-99)")
    team_b_revealed_squares = models.JSONField(default=list, verbose_name="Carrés révélés équipe B (0-99)")
    team_a_photo_revealed = models.BooleanField(default=False, verbose_name="Photo équipe A révélée")
    team_b_photo_revealed = models.BooleanField(default=False, verbose_name="Photo équipe B révélée")
    
    # Définition en cours
    current_definition = models.ForeignKey(Definition, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Définition actuelle")
    revealed_words = models.JSONField(default=list, verbose_name="Mots révélés de la définition")
    last_revealed_word = models.CharField(max_length=100, blank=True, default='', verbose_name="Dernier mot révélé")
    
    # Historique des définitions et photos utilisées
    used_definitions = models.JSONField(default=list, verbose_name="IDs des définitions déjà utilisées")
    used_photos = models.JSONField(default=list, verbose_name="IDs des photos déjà utilisées")
    
    is_active = models.BooleanField(default=True, verbose_name="Partie active")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
            verbose_name = "Partie"
            verbose_name_plural = "Parties"
            constraints = [
                models.UniqueConstraint(
                    fields=['is_active'],
                    condition=models.Q(is_active=True),
                    name="unique_active_game_session"
                )
            ]

    def clean(self):
        # Empêche la création de plusieurs GameSession actives
        if self.is_active:
            qs = GameSession.objects.filter(is_active=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError("Il existe déjà une fête active. Vous ne pouvez pas en créer une nouvelle tant qu'elle n'est pas terminée.")
    
    def __str__(self):
        return f"{self.name} - {self.team_a_name} vs {self.team_b_name}"
