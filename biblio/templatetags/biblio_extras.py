from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Split a string by the given argument"""
    if value:
        return value.split(arg)
    return []

@register.filter
def trim(value):
    """Trim whitespace from a string"""
    if value:
        return value.strip()
    return value
