from django.contrib.contenttypes.models import ContentType

class RelationNotFound(Exception):
    pass

def get_related_objects(queryset, relation_name):
    """
    Efficiently get the objects in a reverse ForeignKey relationship for all
    items in a queryset.

    ``relation_name`` is the name of the reverse relationship on the model -
    normally foo_set if you have not assigned a specific related_name.

    The related items will be stored in a list attached to a ``_foo_set``
    attribute on each item in the queryset, again using the relation_name
    prefixed with an extra underscore.
    """
    # find the relation we're interested in
    rel = None
    for relation in queryset.model._meta.get_all_related_objects():
        if relation.get_accessor_name() == relation_name:
            rel = relation
            break
    if not rel:
        raise RelationNotFound("Relation '%s' not found in model %s" %
                               (relation_name, queryset.model.__name__))

    # rel.field.get_attname gives us the underlying ID field for the
    # related object
    related_field = rel.field.get_attname()

    # put all the queryset items into a dictionary keyed by pk
    obj_dict = dict([(obj.pk, obj) for obj in queryset])

    objects = rel.model.objects.filter(**{"%s__in" % rel.field.name: queryset})

    # now put the results into another dictionary keyed by related ID
    relation_dict = {}
    for obj in objects:
        related_id = getattr(obj, related_field)
        relation_dict.setdefault(related_id, []).append(obj)

    # finally, associate each set of related items with its parent object
    for id, related_items in relation_dict.items():
        setattr(obj_dict[id], "_%s" % relation_name, related_items)
    
    return queryset


def get_generic_relations(queryset, related_name='content_object'):
    """
    Get the objects generically related to each element in a queryset.

    This is the 'forwards' relationship: ie, the queryset elements themselves
    have the ``GenericForeignKey`` field, allowing them to be related to any 
    other single object.

    Once again, the ``related_name`` parameter is the name of the
    GenericForeignKey.

    Each element in the queryset will have its ``_content_object_cache`` element 
    populated with the correct object, exactly as if item.content_object had
    been evaluated separately for each item.

    Note that this function uses n+1 queries, where n is the number of separate
    content types used in the queryset.
    """
    # find the GenericForeignKey we're interested in
    rel = None
    for relation in queryset.model._meta.virtual_fields:
        if relation.name == related_name:
            rel = relation
            break
    if not rel:
        raise RelationNotFound("GenericForeignKey '%s' not found in model %s" %
                               (related_name, queryset.model.__name__))

    # find out which contenttype each queryset element is related to
    ct_id_field = queryset.model._meta.get_field(rel.ct_field)
    generics = {}
    for item in queryset:
        ct_id = getattr(item, ct_id_field.get_attname())
        fk_id = getattr(item, rel.fk_field)
        generics.setdefault(ct_id, set()).add(fk_id)

    # in_bulk gives us a nice dictionary keyed by id
    content_types = ContentType.objects.in_bulk(generics.keys())

    # now do a single query per contenttype
    # and put it into a nested dictionary keyed by ct and id
    relations = {}
    for ct, fk_list in generics.items():
        ct_model = content_types[ct].model_class()
        relations[ct] = ct_model.objects.in_bulk(list(fk_list))

    for item in queryset:
        ct_id = getattr(item, ct_id_field.get_attname())
        fk_id = getattr(item, rel.fk_field)
        setattr(item, rel.cache_attr, relations[ct_id][fk_id])

    return queryset


def get_generic_related_objects(queryset, relation_name):
    """
    Efficiently get the generic relations for every element in a queryset.

    This is the "backwards" generic relation: that is, the source items have the
    ``GenericRelation``, and are therefore related to none, one or several items
    in the model with the ``GenericForeignKey`` field.

    Although generic relations allow you not to define the ``GenericRelation`` 
    field on a model, this function will only work with models where it has been
    defined.

    As with ``get_related_object()`` above, here ``relation_name`` is the name 
    of the ``GenericRelation`` field - and the related objects will be cached in
    the ``_foo`` attribute of the model where foo is the value of relation_name.
    """
    # find the GenericRelation we're interested in
    # they're stored as ManyToMany fields under the hood
    rel = None
    for relation in queryset.model._meta.many_to_many:
        if relation.name == relation_name:
            rel = relation
            break
    if not rel:
        raise RelationNotFound("GenericRelation '%s' not found in model %s" %
                               (relation_name, queryset.model.__name__))

    # get the model and fields the genericrelation points to
    model = rel.related.parent_model
    ct_field = rel.content_type_field_name
    id_field = rel.object_id_field_name

    # get the contenttype for the queryset's model
    content_type = ContentType.objects.get_for_model(queryset.model)

    obj_ids = [obj.id for obj in queryset]

    # now get all the items with the correct contenttype and object_id
    related_items = model.objects.filter(**{ct_field: content_type,
                                            '%s__in' % id_field: obj_ids})
    # and sort them into a dict keyed by id
    relations = {}
    for item in related_items:
        relations.setdefault(getattr(item, id_field), []).append(item)

    for item in queryset:
        setattr(item, '_%s' % relation_name, relations.get(item.pk))

    return queryset
