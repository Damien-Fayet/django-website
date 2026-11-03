import ipaddress


def client_ip(request):
    """Adresse IP du visiteur, ou None.

    Derrière le tunnel Cloudflare, gunicorn n'écoute que sur 127.0.0.1 : l'IP réelle est dans
    `CF-Connecting-IP`. On ne la croit que si la requête vient de la boucle locale (sinon n'importe
    quel client pourrait l'inventer) ; sinon on prend l'adresse de la connexion.
    """
    if request is None:
        return None
    remote = request.META.get("REMOTE_ADDR") or ""
    candidate = remote
    try:
        if ipaddress.ip_address(remote).is_loopback:
            candidate = request.META.get("HTTP_CF_CONNECTING_IP", "").strip() or remote
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def is_family(user):
    """Le compte est-il marqué « membre de la famille » ? (Faux pour un visiteur anonyme.)"""
    from .models import Profile
    return bool(user and user.is_authenticated and Profile.objects.filter(user=user, is_family=True).exists())


def family_user_ids():
    """Identifiants des comptes marqués « membre de la famille »."""
    from .models import Profile
    return set(Profile.objects.filter(is_family=True).values_list("user_id", flat=True))
