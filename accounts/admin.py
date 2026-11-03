from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import LoginEvent, Profile


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    """Journal en lecture seule ; la vue de synthèse est dans « Suivi » (/avent2026/suivi/)."""

    list_display = ("user", "at", "ip")
    list_filter = ("user",)
    date_hierarchy = "at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ProfileInline(admin.StackedInline):
    """La case « Membre de la famille », directement dans la fiche de l'utilisateur."""

    model = Profile
    can_delete = False
    verbose_name_plural = "Profil"


class ProfileUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = UserAdmin.list_display + ("est_famille",)
    list_filter = UserAdmin.list_filter + ("profile__is_family",)
    list_select_related = ("profile",)

    @admin.display(boolean=True, description="Famille", ordering="profile__is_family")
    def est_famille(self, user):
        profile = getattr(user, "profile", None)
        return bool(profile and profile.is_family)


User = get_user_model()
admin.site.unregister(User)
admin.site.register(User, ProfileUserAdmin)
