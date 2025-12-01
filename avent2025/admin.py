from django.contrib import admin
from django.db import models
from django_ckeditor_5.widgets import CKEditor5Widget

from avent2025.models import UserProfile, Enigme, Devinette, Indice, IndiceDevinette, ScoreConfig, AuditLog
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.utils.html import format_html

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fields = ('currentEnigma', 'erreurEnigma', 'currentDevinette', 'erreurDevinette', 'score', 'is_family', 'derniere_activite_display', 'indices_enigme_reveles', 'indices_devinette_reveles', 'reponses_enigmes', 'reponses_devinettes', 'reponses_enigmes_display', 'reponses_devinettes_display')
    readonly_fields = ('score', 'derniere_activite_display', 'reponses_enigmes_display', 'reponses_devinettes_display')
    
    def derniere_activite_display(self, obj):
        """Affiche la dernière activité de l'utilisateur"""
        last_log = AuditLog.objects.filter(user=obj.user).order_by('-timestamp').first()
        if last_log:
            return format_html(
                '<span style="color: #666;">{}</span><br><span style="font-size: 11px; color: #999;">{}</span>',
                last_log.timestamp.strftime('%d/%m/%Y à %H:%M'),
                last_log.get_action_display()
            )
        return format_html('<span style="color: #999;">Aucune activité</span>')
    derniere_activite_display.short_description = 'Dernière activité'
    
    def reponses_enigmes_display(self, obj):
        """Affiche les réponses validées pour les énigmes"""
        if not obj.reponses_enigmes:
            return format_html('<span style="color: #999;">Aucune réponse enregistrée</span>')
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th style="padding: 5px; border: 1px solid #ddd;">Énigme</th><th style="padding: 5px; border: 1px solid #ddd;">Réponse</th></tr>'
        
        for enigme_id, reponse in sorted(obj.reponses_enigmes.items(), key=lambda x: int(x[0])):
            html += f'<tr><td style="padding: 5px; border: 1px solid #ddd; text-align: center;"><strong>#{enigme_id}</strong></td><td style="padding: 5px; border: 1px solid #ddd;"><code>{reponse}</code></td></tr>'
        
        html += '</table>'
        return format_html(html)
    reponses_enigmes_display.short_description = 'Réponses des énigmes'
    
    def reponses_devinettes_display(self, obj):
        """Affiche les réponses validées pour les devinettes"""
        if not obj.reponses_devinettes:
            return format_html('<span style="color: #999;">Aucune réponse enregistrée</span>')
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th style="padding: 5px; border: 1px solid #ddd;">Devinette</th><th style="padding: 5px; border: 1px solid #ddd;">Réponse</th></tr>'
        
        for devinette_id, reponse in sorted(obj.reponses_devinettes.items(), key=lambda x: int(x[0])):
            html += f'<tr><td style="padding: 5px; border: 1px solid #ddd; text-align: center;"><strong>#{devinette_id}</strong></td><td style="padding: 5px; border: 1px solid #ddd;"><code>{reponse}</code></td></tr>'
        
        html += '</table>'
        return format_html(html)
    reponses_devinettes_display.short_description = 'Réponses des devinettes'

class AccountsUserAdmin(AuthUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_family_member', 'last_activity', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'userprofile_2025__is_family')
    
    def add_view(self, *args, **kwargs):
        self.inlines =[]
        return super(AccountsUserAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines =[UserProfileInline]
        return super(AccountsUserAdmin, self).change_view(*args, **kwargs)
    
    def is_family_member(self, obj):
        """Affiche si l'utilisateur est membre de la famille"""
        if hasattr(obj, 'userprofile_2025'):
            if obj.userprofile_2025.is_family:
                return format_html('<span style="color: #28a745; font-weight: bold;">👨‍👩‍👧‍👦 Famille</span>')
            else:
                return format_html('<span style="color: #6c757d;">Public</span>')
        return '-'
    is_family_member.short_description = 'Type'
    is_family_member.admin_order_field = 'userprofile_2025__is_family'
    
    def last_activity(self, obj):
        """Affiche la dernière activité de l'utilisateur"""
        last_log = AuditLog.objects.filter(user=obj).order_by('-timestamp').first()
        if last_log:
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            diff = now - last_log.timestamp
            
            # Colorier selon la fraîcheur
            if diff < timedelta(hours=1):
                color = '#28a745'  # Vert
                label = 'À l\'instant'
            elif diff < timedelta(days=1):
                color = '#17a2b8'  # Bleu
                label = 'Aujourd\'hui'
            elif diff < timedelta(days=7):
                color = '#ffc107'  # Jaune
                label = 'Cette semaine'
            else:
                color = '#6c757d'  # Gris
                label = last_log.timestamp.strftime('%d/%m/%Y')
            
            return format_html(
                '<span style="color: {}; font-weight: 500;">{}</span><br><span style="font-size: 11px; color: #999;">{}</span>',
                color,
                label,
                last_log.timestamp.strftime('%H:%M')
            )
        return format_html('<span style="color: #dc3545;">Jamais</span>')
    last_activity.short_description = 'Dernière activité'


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
    
    formfield_overrides = {
        models.TextField: {'widget': CKEditor5Widget(config_name='default')},
    }
    
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
    
    formfield_overrides = {
        models.TextField: {'widget': CKEditor5Widget(config_name='default')},
    }

# Configuration pour les Indices d'énigmes
@admin.register(Indice)
class IndiceAdmin(admin.ModelAdmin):
    list_display = ('numero', 'enigme', 'categorie', 'type_indice', 'cout', 'get_texte_court')
    list_filter = ('enigme', 'categorie', 'type_indice', 'cout')
    ordering = ('enigme', 'numero')
    
    formfield_overrides = {
        models.TextField: {'widget': CKEditor5Widget(config_name='default')},
    }
    
    def get_texte_court(self, obj):
        if obj.texte:
            return obj.texte[:50] + '...' if len(obj.texte) > 50 else obj.texte
        return '(image uniquement)'
    get_texte_court.short_description = 'Texte'

# Configuration pour les Indices de devinettes
@admin.register(IndiceDevinette)
class IndiceDevinetteAdmin(admin.ModelAdmin):
    list_display = ('numero', 'enigme', 'categorie', 'type_indice', 'cout', 'get_texte_court')  # Le champ s'appelle 'enigme' dans le modèle
    list_filter = ('enigme', 'categorie', 'type_indice', 'cout')
    ordering = ('enigme', 'numero')
    
    formfield_overrides = {
        models.TextField: {'widget': CKEditor5Widget(config_name='default')},
    }
    
    def get_texte_court(self, obj):
        if obj.texte:
            return obj.texte[:50] + '...' if len(obj.texte) > 50 else obj.texte
        return '(image uniquement)'
    get_texte_court.short_description = 'Texte'


# Configuration des scores
@admin.register(ScoreConfig)
class ScoreConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Points positifs', {
            'fields': ('points_enigme_resolue', 'points_devinette_resolue'),
            'description': 'Points gagnés lors de la résolution'
        }),
        ('Malus (points négatifs)', {
            'fields': ('malus_erreur_enigme', 'malus_erreur_devinette'),
            'description': 'Points perdus lors d\'erreurs'
        }),
    )
    
    def has_add_permission(self, request):
        # Ne permettre qu'une seule instance
        return not ScoreConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Ne pas permettre la suppression
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user_link', 'action_colored', 'enigme_id', 'devinette_id', 'reponse_courte', 'ip_address')
    list_filter = ('action', 'timestamp', 'user')
    search_fields = ('user__username', 'reponse_donnee', 'details', 'ip_address')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    readonly_fields = ('user', 'action', 'timestamp', 'ip_address', 'user_agent', 'enigme_id', 'devinette_id', 'indice_id', 'reponse_donnee', 'details')
    change_list_template = 'admin/avent2025/auditlog/change_list.html'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('user', 'action', 'timestamp')
        }),
        ('Détails de l\'action', {
            'fields': ('enigme_id', 'devinette_id', 'indice_id', 'reponse_donnee', 'details')
        }),
        ('Informations techniques', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Les logs ne peuvent pas être créés manuellement
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Seuls les superusers peuvent supprimer des logs
        return request.user.is_superuser
    
    def user_link(self, obj):
        """Affiche le nom d'utilisateur avec un lien vers son profil"""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.username
        )
    user_link.short_description = 'Utilisateur'
    
    def action_colored(self, obj):
        """Affiche l'action avec une couleur selon le type"""
        colors = {
            'LOGIN': '#28a745',
            'LOGOUT': '#6c757d',
            'ENIGME_SUCCESS': '#28a745',
            'ENIGME_FAIL': '#dc3545',
            'DEVINETTE_SUCCESS': '#28a745',
            'DEVINETTE_FAIL': '#dc3545',
            'ENIGME_VIEW': '#17a2b8',
            'DEVINETTE_VIEW': '#17a2b8',
            'INDICE_REVEAL': '#ffc107',
            'INDICE_DEV_REVEAL': '#ffc107',
            'CLASSEMENT_VIEW': '#6f42c1',
            'HOME_VIEW': '#007bff',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_colored.short_description = 'Action'
    
    def reponse_courte(self, obj):
        """Affiche les 50 premiers caractères de la réponse"""
        if obj.reponse_donnee:
            return obj.reponse_donnee[:50] + ('...' if len(obj.reponse_donnee) > 50 else '')
        return '-'
    reponse_courte.short_description = 'Réponse'
    
    def changelist_view(self, request, extra_context=None):
        """Ajoute des statistiques au contexte"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        extra_context = extra_context or {}
        
        # Total des logs
        extra_context['total_logs'] = AuditLog.objects.count()
        
        # Utilisateurs actifs (ayant au moins une action)
        extra_context['active_users'] = AuditLog.objects.values('user').distinct().count()
        
        # Actions des dernières 24h
        yesterday = timezone.now() - timedelta(days=1)
        extra_context['logs_24h'] = AuditLog.objects.filter(timestamp__gte=yesterday).count()
        
        # Taux de réussite (succès / (succès + échecs))
        success_count = AuditLog.objects.filter(
            action__in=[AuditLog.ENIGME_SUBMIT_SUCCESS, AuditLog.DEVINETTE_SUBMIT_SUCCESS]
        ).count()
        fail_count = AuditLog.objects.filter(
            action__in=[AuditLog.ENIGME_SUBMIT_FAIL, AuditLog.DEVINETTE_SUBMIT_FAIL]
        ).count()
        total_attempts = success_count + fail_count
        extra_context['success_rate'] = round((success_count / total_attempts * 100) if total_attempts > 0 else 0, 1)
        
        return super().changelist_view(request, extra_context=extra_context)
