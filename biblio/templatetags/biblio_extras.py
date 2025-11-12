from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Split a string by the given argument"""
    if value:
        return value.split(arg)
    return []

@register.filter
def strip(value):
    """Strip whitespace from a string"""
    if value:
        return value.strip()
    return value

@register.filter
def star_range(rating):
    """Return a range for filled stars based on rating"""
    try:
        rating_int = int(float(rating))
        return range(rating_int)
    except (ValueError, TypeError):
        return range(0)

@register.filter
def empty_star_range(rating):
    """Return a range for empty stars based on rating"""
    try:
        rating_int = int(float(rating))
        return range(5 - rating_int)
    except (ValueError, TypeError):
        return range(5)

@register.filter
def trim(value):
    """Alias for strip - remove whitespace from a string"""
    if value:
        return value.strip()
    return value
