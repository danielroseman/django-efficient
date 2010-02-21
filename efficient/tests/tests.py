from django.test import TestCase
from django.conf import settings
from django.core.management import call_command
from django.contrib.contenttypes.models import ContentType
from django.db.models import loading
from django.db import connection, reset_queries
from efficient.utils import get_related_objects, get_generic_relations, get_generic_related_objects, RelationNotFound
from efficient.tests.models import Article, Gallery, Category, Asset

class EfficientTest(TestCase):
    def setUp(self):
        self.original_installed_apps = settings.INSTALLED_APPS
        if 'efficient.tests' not in settings.INSTALLED_APPS:
            settings.INSTALLED_APPS += ('efficient.tests',)
        if not hasattr(self, 'original_debug'):
            self.original_debug = settings.DEBUG
            settings.DEBUG = True
        loading.cache.loaded = False
        call_command('syncdb', verbosity=0)
        cat1 = Category.objects.create(name='cat1')
        cat2 = Category.objects.create(name='cat2')

        for i in range(1, 11):
            a1 = Article.objects.create(name='article%s_cat1' % i, category=cat1)
            a2 = Article.objects.create(name='article%s_cat2' % i, category=cat2)
            g1 = Gallery.objects.create(name='gallery%s_cat1' % i, category=cat1)
            g2 = Gallery.objects.create(name='gallery%s_cat2' % i, category=cat2)

            for j in range(1, 6):
                a1.assets.create(name='%s_asset%s' % (a1.name, j))
                a2.assets.create(name='%s_asset%s' % (a2.name, j))
                g1.assets.create(name='%s_asset%s' % (g1.name, j))
                g2.assets.create(name='%s_asset%s' % (g2.name, j))

        ContentType.objects.clear_cache()
        reset_queries()

    def tearDown(self):
        settings.INSTALLED_APPS = self.original_installed_apps
        loading.cache.loaded = False
        call_command('syncdb', verbosity=0)
        settings.DEBUG = self.original_debug

    def test_initial_objects(self):
        """Check that we start with the right amount of data"""

        self.assertEquals(Article.objects.count(), 20)
        self.assertEquals(Gallery.objects.count(), 20)
        self.assertEquals(Asset.objects.count(), 200)

        a1 = Article.objects.all()[0]
        self.assertEquals(a1.assets.count(), 5)

    def test_related_objects(self):
        """
        Check that get_related_objects correctly populates the _article_set
        attribute of each element that has a foreign key pointing at it, in
        fewer queries than simply iterating through the reverse relations.
        """
        categories = Category.objects.all()
        list(categories)
        articles_original = list(categories[0].article_set.all())
        articles_original.extend(list(categories[1].article_set.all()))
        self.assertEquals(len(connection.queries), 3)
        self.assertEqual(len(articles_original), 20)

        reset_queries()
        ContentType.objects.clear_cache()
        # slightly cheating here, as we still have categories from before
        # but still should expect 1 query to get articles rather than 2
        get_related_objects(categories, 'article_set')
        articles_efficient = categories[0]._article_set[:]
        articles_efficient.extend(categories[1]._article_set)
        self.assertEquals(len(connection.queries), 1)
        self.assertEquals(len(articles_efficient), 20)

        self.assertEquals(articles_original, articles_efficient)

        self.assertRaises(RelationNotFound, get_related_objects, categories,
                          'nonexistent_set')

    def test_generic_relations(self):
        """
        Check that get_generic_relations correctly populates the
        _content_object_cache of each element with a GenericForeignKey, in fewer
        queries than simply iterating through and checking x.content_object.
        """
        assets = Asset.objects.all()
        related_items = set([a.content_object for a in assets])
        # needed 1 query to get assets, 2 for contenttypes (article and gallery)
        # and 200 for the actual items (even though there are only 40)
        self.assertEquals(len(connection.queries), 203)
        self.assertEquals(len(related_items), 40)

        reset_queries()
        ContentType.objects.clear_cache()
        get_generic_relations(assets)
        for asset in assets:
            self.assertTrue(hasattr(asset, '_content_object_cache'))
            self.assertEquals(asset.content_object.id, asset.object_id)
        # should have one query to get the contenttypes, then one per type
        self.assertEquals(len(connection.queries), 3)

        self.assertRaises(RelationNotFound, get_generic_relations, assets,
                          'nonexistentrelationship')

    def test_generic_related_objects(self):
        """
        Check that get_generic_related_objects correctly populates the _assets
        attribute of each element with a GenericRelation, in fewer queries than
        simply iterating through and checking x.assets.all().
        """
        articles = Article.objects.all()
        assets_original = []
        for article in articles:
            assets_original.extend(list(article.assets.all()))
        self.assertEquals(len(connection.queries), 22)
        self.assertEquals(len(assets_original), 100)

        reset_queries()
        ContentType.objects.clear_cache()
        get_generic_related_objects(articles, 'assets')
        assets_efficient = []
        for article in articles:
            assets_efficient.extend(article._assets)
            for asset in article._assets:
                self.assertEquals(asset.object_id, article.id)
        self.assertEquals(len(assets_efficient), 100)
        self.assertEquals(assets_efficient, assets_original)
        # one query to get contenttype, then one to get all assets
        self.assertEquals(len(connection.queries), 2)

        self.assertRaises(RelationNotFound, get_generic_related_objects,
                          articles, 'nonexistentrelationship')
