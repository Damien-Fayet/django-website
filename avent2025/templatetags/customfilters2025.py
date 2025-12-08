from django import template

register = template.Library()

@register.filter
def get_by_index(l, i):
    return l[i]

@register.filter
def get_item(dictionary, key):
    """Récupère un élément d'un dictionnaire par sa clé"""
    return dictionary.get(key)

@register.filter
def divide(value, arg):
    """Divise la valeur par l'argument"""
    try:
        return int(float(value) / float(arg))
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def modulo(value, arg):
    """Retourne le reste de la division (modulo)"""
    try:
        return int(float(value)) % int(float(arg))
    except (ValueError, ZeroDivisionError):
        return 0