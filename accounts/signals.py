from .models import LoginEvent


def record_login(sender, user, request, **kwargs):
    """Une ligne par connexion réelle (pas par visite : la session reste ouverte plusieurs jours)."""
    LoginEvent.objects.create(user=user)
