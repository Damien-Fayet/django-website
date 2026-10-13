from django.contrib import admin

from .models import LoginEvent


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
