from django.contrib import admin
from .models import ChessGame, MoveAnalysis


@admin.register(ChessGame)
class ChessGameAdmin(admin.ModelAdmin):
    list_display = ['username', 'white_player', 'black_player', 'result', 'start_time', 'analyzed']
    list_filter = ['analyzed', 'rated', 'result', 'start_time']
    search_fields = ['username', 'white_player', 'black_player', 'game_id']
    readonly_fields = ['game_id', 'created_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('username', 'game_id', 'game_url')
        }),
        ('Joueurs et résultat', {
            'fields': ('white_player', 'black_player', 'result', 'rated')
        }),
        ('Timing', {
            'fields': ('time_control', 'start_time', 'end_time')
        }),
        ('Données de la partie', {
            'fields': ('pgn', 'moves_data', 'analyzed')
        }),
        ('Métadonnées', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )


@admin.register(MoveAnalysis)
class MoveAnalysisAdmin(admin.ModelAdmin):
    list_display = ['game', 'move_number', 'move_notation', 'quality', 'evaluation_before', 'evaluation_after']
    list_filter = ['quality', 'game__start_time']
    search_fields = ['game__username', 'move_notation', 'best_move']
    
    fieldsets = (
        ('Coup', {
            'fields': ('game', 'move_number', 'move_notation')
        }),
        ('Évaluation', {
            'fields': ('evaluation_before', 'evaluation_after', 'quality', 'best_move')
        }),
        ('Positions', {
            'fields': ('fen_before', 'fen_after'),
            'classes': ('collapse',)
        })
    )
