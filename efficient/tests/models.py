"""Models for testing purposes only."""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic


class Category(models.Model):
    name = models.CharField(max_length=100)

class Asset(models.Model):
    name = models.CharField(max_length=100)
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey()

class Article(models.Model):
    category = models.ForeignKey(Category)
    name = models.CharField(max_length=100)
    assets = generic.GenericRelation(Asset)

class Gallery(models.Model):
    category = models.ForeignKey(Category)
    name = models.CharField(max_length=100)
    assets = generic.GenericRelation(Asset)

