from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def extract_game_id(url):
    """Extraire l'ID du jeu depuis l'URL Chess.com"""
    try:
        if url and '/game/live/' in url:
            return url.split('/')[-1]
        return url
    except Exception:
        return url

@register.filter
def format_time_control(time_control):
    """Formater le contrôle de temps"""
    try:
        if '+' in time_control:
            base, increment = time_control.split('+')
            base_min = int(base) // 60
            increment_sec = int(increment)
            return f"{base_min}+{increment_sec}"
        else:
            minutes = int(time_control) // 60
            return f"{minutes} min"
    except Exception:
        return time_control

@register.filter
def get_player_result_class(result):
    """Retourner la classe CSS selon le résultat"""
    if result in ['win', 'checkmated']:
        return 'text-success'
    elif result in ['loss', 'timeout', 'resigned']:
        return 'text-danger'
    elif result in ['agreed', 'stalemate', 'repetition', 'insufficient']:
        return 'text-warning'
    else:
        return 'text-muted'  # Pour unknown ou autres

@register.filter
def format_result(result):
    """Formater le résultat du joueur"""
    result_map = {
        'win': 'Victoire',
        'loss': 'Défaite',
        'checkmated': 'Échec et mat',
        'timeout': 'Temps écoulé',
        'resigned': 'Abandon',
        'agreed': 'Nulle',
        'stalemate': 'Pat',
        'repetition': 'Répétition',
        'insufficient': 'Matériel insuffisant',
    }
    return result_map.get(result, result.title() if result != 'unknown' else '')

@register.filter
def multiply(value, arg):
    """Multiplier deux nombres"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Diviser deux nombres"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def format_evaluation(centipawns):
    """Formater une évaluation en centipawns vers pions avec badge coloré"""
    try:
        # Convertir en pions (diviser par 100)
        pawns = float(centipawns) / 100.0
        
        # Déterminer la couleur du badge selon le signe
        if pawns >= 0:
            badge_class = 'bg-light text-dark border border-secondary'
            label = 'Blanc'
            sign = '+'
        else:
            badge_class = 'bg-dark text-white'
            label = 'Noir'
            sign = ''  # Le signe moins est déjà dans la valeur
        
        # Retourner le HTML du badge
        return mark_safe(f'<span class="badge {badge_class}" title="Avantage pour les {label}s">{sign}{pawns:.2f}</span>')
    except (ValueError, TypeError):
        return mark_safe('<span class="badge bg-secondary">?</span>')

@register.filter
def centipawns_to_pawns(centipawns):
    """Convertir des centipawns en pions"""
    try:
        return float(centipawns) / 100.0
    except (ValueError, TypeError):
        return 0
