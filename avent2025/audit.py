"""
Utilitaires pour l'audit logging
"""
from .models import AuditLog


def get_client_ip(request):
    """Récupère l'adresse IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_action(user, action, request=None, **kwargs):
    """
    Crée une entrée d'audit log
    
    Args:
        user: L'utilisateur qui effectue l'action
        action: Le type d'action (utiliser les constantes AuditLog.*)
        request: L'objet HttpRequest (optionnel)
        **kwargs: Champs additionnels (enigme_id, devinette_id, indice_id, reponse_donnee, details)
    
    Returns:
        L'objet AuditLog créé
    """
    log_data = {
        'user': user,
        'action': action,
    }
    
    # Ajouter les infos de la requête si disponibles
    if request:
        log_data['ip_address'] = get_client_ip(request)
        log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limiter la taille
    
    # Ajouter les champs additionnels
    for key, value in kwargs.items():
        if key in ['enigme_id', 'devinette_id', 'indice_id', 'reponse_donnee', 'details']:
            log_data[key] = value
    
    return AuditLog.objects.create(**log_data)
