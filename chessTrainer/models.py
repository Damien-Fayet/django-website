from django.db import models
from django.utils import timezone
import json


class PlayerSyncStatus(models.Model):
    """Modèle pour stocker l'état de synchronisation des parties d'un joueur"""
    
    username = models.CharField(max_length=100, unique=True, help_text="Nom d'utilisateur Chess.com")
    last_sync_time = models.DateTimeField(default=timezone.now, help_text="Dernière synchronisation")
    last_game_end_time = models.DateTimeField(null=True, blank=True, help_text="Timestamp de la dernière partie récupérée")
    total_games_count = models.IntegerField(default=0, help_text="Nombre total de parties connues")
    sync_count = models.IntegerField(default=0, help_text="Nombre de synchronisations effectuées")
    
    class Meta:
        ordering = ['-last_sync_time']
        
    def __str__(self):
        return f"Sync {self.username} - {self.total_games_count} parties"


class ChessGame(models.Model):
    """Modèle pour stocker les informations d'une partie d'échecs"""
    
    username = models.CharField(max_length=100, help_text="Nom d'utilisateur Chess.com")
    game_id = models.CharField(max_length=50, unique=True, help_text="ID unique de la partie")
    game_url = models.URLField(help_text="URL de la partie sur Chess.com")
    
    # Informations sur la partie
    white_player = models.CharField(max_length=100)
    black_player = models.CharField(max_length=100)
    time_control = models.CharField(max_length=50)
    rated = models.BooleanField(default=True)
    result = models.CharField(max_length=20)  # "win", "checkmated", "agreed", "timeout", etc.
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # PGN et analyse
    pgn = models.TextField(help_text="Notation PGN de la partie")
    moves_data = models.JSONField(default=dict, help_text="Données des coups avec évaluations")
    
    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    analyzed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-start_time']
        
    def __str__(self):
        return f"{self.white_player} vs {self.black_player} ({self.start_time.date()})"
    
    def get_errors(self):
        """Retourne les coups considérés comme des erreurs"""
        errors = []
        if self.moves_data and 'moves' in self.moves_data:
            for move in self.moves_data['moves']:
                if move.get('accuracy') and move['accuracy'] < 80:  # Seuil d'erreur
                    errors.append(move)
        return errors
    
    def get_blunders(self):
        """Retourne les grosses erreurs (blunders)"""
        blunders = []
        if self.moves_data and 'moves' in self.moves_data:
            for move in self.moves_data['moves']:
                if move.get('accuracy') and move['accuracy'] < 50:  # Seuil de blunder
                    blunders.append(move)
        return blunders


class MoveAnalysis(models.Model):
    """Modèle pour l'analyse détaillée des coups"""
    
    MOVE_QUALITY_CHOICES = [
        ('brilliant', 'Brillant'),
        ('great', 'Excellent'),
        ('best', 'Meilleur'),
        ('good', 'Bon'),
        ('inaccuracy', 'Imprécision'),
        ('mistake', 'Erreur'),
        ('blunder', 'Gaffe'),
    ]
    
    game = models.ForeignKey(ChessGame, on_delete=models.CASCADE, related_name='move_analyses')
    move_number = models.IntegerField()
    move_notation = models.CharField(max_length=10)  # e4, Nf3, etc.
    
    # Évaluation du coup
    evaluation_before = models.FloatField(null=True, blank=True)  # Évaluation avant le coup
    evaluation_after = models.FloatField(null=True, blank=True)   # Évaluation après le coup
    quality = models.CharField(max_length=20, choices=MOVE_QUALITY_CHOICES, null=True, blank=True)
    
    # Position FEN
    fen_before = models.TextField()  # Position avant le coup
    fen_after = models.TextField()   # Position après le coup
    
    # Coup recommandé par l'engine
    best_move = models.CharField(max_length=10, null=True, blank=True)
    
    class Meta:
        ordering = ['move_number']
        unique_together = ['game', 'move_number']
        
    def __str__(self):
        return f"Coup {self.move_number}: {self.move_notation} ({self.quality or 'Non évalué'})"


class TrainingPosition(models.Model):
    """Modèle pour les positions d'entraînement basées sur les erreurs du joueur"""
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Facile'),
        ('medium', 'Moyen'),
        ('hard', 'Difficile'),
    ]
    
    username = models.CharField(max_length=100, help_text="Joueur qui s'entraîne")
    original_game = models.ForeignKey(ChessGame, on_delete=models.CASCADE, help_text="Partie d'origine")
    move_analysis = models.ForeignKey(MoveAnalysis, on_delete=models.CASCADE, help_text="Coup d'origine analysé")
    
    # Position d'entraînement
    fen_position = models.TextField(help_text="Position FEN à partir de laquelle l'utilisateur doit jouer")
    player_color = models.CharField(max_length=5, choices=[('white', 'Blanc'), ('black', 'Noir')])
    
    # Coup original (erreur)
    original_move = models.CharField(max_length=10, help_text="Coup original (erreur) du joueur")
    original_evaluation = models.FloatField(help_text="Évaluation après le coup original")
    
    # Meilleur coup selon Stockfish
    best_move = models.CharField(max_length=10, help_text="Meilleur coup recommandé")
    best_evaluation = models.FloatField(help_text="Évaluation après le meilleur coup")
    
    # Variantes alternatives
    alternative_moves = models.JSONField(default=list, help_text="Liste des coups alternatifs avec évaluations")
    
    # Métadonnées
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    times_played = models.IntegerField(default=0)
    times_solved = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['username', 'original_game', 'move_analysis']
    
    def __str__(self):
        return f"Position d'entraînement pour {self.username} - Coup {self.move_analysis.move_number}"
    
    @property
    def success_rate(self):
        """Taux de réussite de cette position"""
        if self.times_played == 0:
            return 0
        return (self.times_solved / self.times_played) * 100


class TrainingAttempt(models.Model):
    """Modèle pour enregistrer les tentatives d'entraînement"""
    
    RESULT_CHOICES = [
        ('perfect', 'Parfait'),
        ('good', 'Bon'),
        ('suboptimal', 'Sous-optimal'),
        ('poor', 'Mauvais'),
        ('blunder', 'Gaffe'),
    ]
    
    training_position = models.ForeignKey(TrainingPosition, on_delete=models.CASCADE, related_name='attempts')
    
    # Coup joué par l'utilisateur
    attempted_move = models.CharField(max_length=10, help_text="Coup tenté par l'utilisateur")
    evaluation_after_attempt = models.FloatField(help_text="Évaluation après le coup tenté")
    
    # Analyse de la tentative
    result_quality = models.CharField(max_length=10, choices=RESULT_CHOICES)
    improvement_points = models.FloatField(help_text="Points d'amélioration par rapport au coup original")
    is_better_than_original = models.BooleanField(default=False)
    is_best_move = models.BooleanField(default=False)
    
    # Métadonnées
    attempt_time = models.DateTimeField(default=timezone.now)
    time_spent_seconds = models.IntegerField(default=0, help_text="Temps passé à réfléchir (en secondes)")
    
    class Meta:
        ordering = ['-attempt_time']
    
    def __str__(self):
        return f"Tentative {self.attempted_move} - {self.result_quality} ({self.improvement_points:+.2f} points)"


class TrainingSession(models.Model):
    """Modèle pour suivre les sessions d'entraînement"""
    
    username = models.CharField(max_length=100)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # Statistiques de la session
    positions_attempted = models.IntegerField(default=0)
    positions_solved = models.IntegerField(default=0)
    total_improvement_points = models.FloatField(default=0.0)
    
    # Paramètres de la session
    difficulty_filter = models.CharField(max_length=10, default='all')
    max_positions = models.IntegerField(default=10)
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Session {self.username} - {self.start_time.date()} ({self.positions_solved}/{self.positions_attempted})"
    
    @property
    def success_rate(self):
        """Taux de réussite de la session"""
        if self.positions_attempted == 0:
            return 0
        return (self.positions_solved / self.positions_attempted) * 100
    
    @property
    def duration_minutes(self):
        """Durée de la session en minutes"""
        if not self.end_time:
            return 0
        return (self.end_time - self.start_time).total_seconds() / 60
