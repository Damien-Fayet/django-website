from django.conf import settings

def discord_url(request):
    """Rend l'URL Discord disponible dans tous les templates"""
    return {
        'DISCORD_INVITE_URL': getattr(settings, 'DISCORD_INVITE_URL', None)
    }
