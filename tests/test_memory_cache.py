import cachefs
import unittest
from test_helper import TestHelper
import time

class CacheFsUnitTest(unittest.TestCase):

    def setUp(self):
        cachefs.memory_cache.time = time # FIXME:
        self.sut = cachefs.CacheFs()
        self.sut.cfg = TestHelper.get_cfg()

    def tearDown(self):
        pass

    def test_memory_cache_getAttributes(self):
        memory_cache = self._create_memory_cache()

        root_path = "/"
        root_stat = 54321
        self.assertEqual(None, memory_cache.getAttributes(root_path))
        memory_cache.cacheAttributes(root_path, root_stat)
        self.assertEqual(root_stat, memory_cache.getAttributes(root_path).stat)

        some_stat = 12345
        some_path = "/example/file"
        self.assertEqual(None, memory_cache.getAttributes(some_path))
        memory_cache.cacheAttributes(some_path, some_stat)
        self.assertEqual(some_stat, memory_cache.getAttributes(some_path).stat)

    def test_memory_cache_cacheLinkTarget(self):
        memory_cache = self._create_memory_cache()
        some_target = "target"
        some_path = "/example/link"
        self.assertEqual(None, memory_cache.readLink(some_path))
        memory_cache.cacheLinkTarget(some_path, some_target)
        self.assertEqual(some_target, memory_cache.readLink(some_path).target)

    def test_memory_cache_listDirectory(self):
        memory_cache = self._create_memory_cache()
        memory_cache.cacheAttributes('/', 1)
        memory_cache.cacheAttributes('/home', 2)
        memory_cache.cacheAttributes('/home/a', 3)
        memory_cache.cacheAttributes('/home/b', 4)

        memory_cache.hasAllChildrenAttributesCached('/', True)
        self.assertEqual(['home'], memory_cache.listDirectory('/'))

        memory_cache.hasAllChildrenAttributesCached('/home', True)
        self.assertEqual(['a', 'b'], memory_cache.listDirectory('/home'))

    def _create_memory_cache(self):
        return cachefs.MemoryCache(self.sut.cfg.cache_manager.memory_cache_lifetime)
