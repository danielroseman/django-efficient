from django.template import Node, TemplateSyntaxError, Library, Variable
from efficient import utils

register = Library()

@register.simple_tag
def resolve_generics(queryset, relation_name=None):
    if relation_name is not None:
        utils.get_generic_relations(queryset, relation_name)
    else:
        utils.get_generic_relations(queryset)
    return ''

@register.simple_tag
def get_generic_related_objects(queryset, relation_name):
    utils.get_generic_related_objects(queryset, relation_name)


