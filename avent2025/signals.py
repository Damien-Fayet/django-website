"""
Signaux pour logger les connexions et déconnexions
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import AuditLog
from .audit import log_action


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log quand un utilisateur se connecte"""
    log_action(user, AuditLog.LOGIN, request)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log quand un utilisateur se déconnecte"""
    if user:  # user peut être None si la session a expiré
        log_action(user, AuditLog.LOGOUT, request)
