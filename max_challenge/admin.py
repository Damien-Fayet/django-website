from django.contrib import admin
from django.utils.html import format_html
from .models import Photo, Definition, GameSession

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_preview', 'image_400_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name',)
    fields = ('name', 'image', 'image_400_display')
    readonly_fields = ('image_400_display',)
    
    @admin.display(description="Aperçu")
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;">', obj.image.url)
        return "Pas d'image"
    
    @admin.display(description="Image 400x400")
    def image_400_preview(self, obj):
        if obj.image_400x400:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;">', obj.image_400x400.url)
        return "Pas encore générée"
    
    @admin.display(description="Image 400x400 complète")
    def image_400_display(self, obj):
        if obj.image_400x400:
            return format_html('<img src="{}" style="width: 400px; height: 400px; border: 2px solid #ccc;">', obj.image_400x400.url)
        return "L'image 400x400 sera générée automatiquement après sauvegarde"

@admin.register(Definition)
class DefinitionAdmin(admin.ModelAdmin):
    list_display = ('word', 'definition_preview', 'difficulty', 'created_at')
    list_filter = ('difficulty', 'created_at')
    search_fields = ('word', 'definition')
    fields = ('word', 'definition', 'difficulty')
    
    @admin.display(description="Définition")
    def definition_preview(self, obj):
        return obj.definition[:100] + "..." if len(obj.definition) > 100 else obj.definition

@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Interdit l'ajout si une GameSession existe déjà
        if GameSession.objects.exists():
            return False
        return super().has_add_permission(request)

    def get_actions(self, request):
        # Désactive l'action "Supprimer la sélection" si une GameSession existe
        actions = super().get_actions(request)
        if GameSession.objects.exists() and 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    list_display = ('name', 'team_a_name', 'team_b_name', 'team_a_score', 'team_b_score', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'team_a_name', 'team_b_name')
    filter_horizontal = ('global_photos',)
    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'is_active')
        }),
        ('Configuration', {
            'fields': ('max_teams', 'points_per_correct', 'squares_per_reveal', 'ascii_reveal_speed', 'definition_reveal_speed')
        }),
        ('Équipes', {
            'fields': ('team_a_name', 'team_b_name', 'team_a_photo', 'team_b_photo')
        }),
        ('Scores', {
            'fields': ('team_a_score', 'team_b_score')
        }),
        ('Image globale', {
            'fields': ('global_photos',)
        }),
        ('Définition en cours', {
            'fields': ('current_definition',)
        }),
        ('État du jeu (automatique)', {
            'fields': ('team_a_revealed_squares', 'team_b_revealed_squares', 'team_a_photo_revealed', 'team_b_photo_revealed', 'revealed_words', 'used_definitions', 'used_photos'),
            'classes': ('collapse',)
        })
    )
