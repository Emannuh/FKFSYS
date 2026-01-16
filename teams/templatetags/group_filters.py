from django import template

register = template.Library()

def parse_group_list(value):
    if isinstance(value, str):
        return [v.strip() for v in value.split(',')]
    return value

@register.filter
def has_group(user, group_names):
    """
    Usage: {% if user|has_group:"Group1,Group2" %}
    Returns True if user is in any of the given groups.
    """
    if user.is_anonymous:
        return False
    group_list = parse_group_list(group_names)
    return user.groups.filter(name__in=group_list).exists()
