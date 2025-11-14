from django.contrib import admin

from avent2025.models import UserProfile, Enigme, Devinette, Indice, IndiceDevinette
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

class AccountsUserAdmin(AuthUserAdmin):
    def add_view(self, *args, **kwargs):
        self.inlines =[]
        return super(AccountsUserAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines =[UserProfileInline]
        return super(AccountsUserAdmin, self).change_view(*args, **kwargs)


admin.site.unregister(User)
admin.site.register(User, AccountsUserAdmin)

# Configuration améliorée pour les Énigmes
@admin.register(Enigme)
class EnigmeAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'date_dispo', 'is_dispo', 'nb_indices')
    list_filter = ('date_dispo',)
    search_fields = ('titre', 'texte', 'reponse')
    date_hierarchy = 'date_dispo'
    ordering = ('id',)
    
    def nb_indices(self, obj):
        return Indice.objects.filter(enigme=obj).count()
    nb_indices.short_description = 'Nombre d\'indices'

# Configuration améliorée pour les Devinettes
@admin.register(Devinette)
class DevinetteAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'genre', 'date_dispo', 'is_dispo')
    list_filter = ('genre', 'date_dispo')
    search_fields = ('titre', 'texte', 'reponse')
    date_hierarchy = 'date_dispo'
    ordering = ('id',)

# Configuration pour les Indices d'énigmes
@admin.register(Indice)
class IndiceAdmin(admin.ModelAdmin):
    list_display = ('numero', 'enigme', 'categorie', 'cout', 'get_texte_court')
    list_filter = ('enigme', 'categorie', 'cout')
    ordering = ('enigme', 'numero')
    
    def get_texte_court(self, obj):
        if obj.texte:
            return obj.texte[:50] + '...' if len(obj.texte) > 50 else obj.texte
        return '(image uniquement)'
    get_texte_court.short_description = 'Texte'

# Configuration pour les Indices de devinettes
@admin.register(IndiceDevinette)
class IndiceDevinetteAdmin(admin.ModelAdmin):
    list_display = ('numero', 'enigme', 'categorie', 'cout', 'get_texte_court')  # Le champ s'appelle 'enigme' dans le modèle
    list_filter = ('enigme', 'categorie', 'cout')
    ordering = ('enigme', 'numero')
    
    def get_texte_court(self, obj):
        if obj.texte:
            return obj.texte[:50] + '...' if len(obj.texte) > 50 else obj.texte
        return '(image uniquement)'
    get_texte_court.short_description = 'Texte'
