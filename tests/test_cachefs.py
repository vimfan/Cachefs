import cachefs
import mox
import unittest
import time
import errno
import os
import fuse

from test_helper import TestHelper

class CacheFsUnitTest(unittest.TestCase):

    def setUp(self):
        cachefs.memory_cache.time = time # FIXME:
        self.sut = cachefs.CacheFs()
        self.sut.cfg = TestHelper.get_cfg()

    def tearDown(self):
        pass

    def test_access(self):
        # inject mock
        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)

        # setup mock
        cacheManagerMock.exists('file1').AndReturn(True)
        cacheManagerMock.exists('file2').AndReturn(False)
        cacheManagerMock.exists('file3').AndReturn(True)
        mox.Replay(cacheManagerMock)

        failure = -errno.EACCES
        success = 0
        self.assertEqual(success, self.sut.access('file1', os.F_OK));
        self.assertEqual(failure, self.sut.access('file2', os.F_OK));
        self.assertEqual(success, self.sut.access('file3', os.F_OK));
        self.assertEqual(failure, self.sut.access('file3', os.W_OK));
        self.assertEqual(success, self.sut.access('file4', os.R_OK | os.X_OK));

    def test_readdir(self):
        DIRPATH = '/DIR'
        dir_entries = ['file', 'subdir', 'file2']

        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)
        cacheManagerMock.exists(DIRPATH).AndReturn(True)
        cacheManagerMock.isDirectory(DIRPATH).AndReturn(True)
        cacheManagerMock.listDirectory(DIRPATH).AndReturn(dir_entries)
        mox.Replay(cacheManagerMock)

        dir_entries_match = dir_entries + ['.', '..']
        readdir_entries = []

        for entry in self.sut.readdir(DIRPATH, 0, ''):
            self.assertTrue(isinstance(entry, fuse.Direntry))
            self.assertTrue(entry.name in dir_entries_match)
            readdir_entries.append(entry.name)

        self.assertEqual(sorted(dir_entries_match), sorted(readdir_entries))

    def test_readdir_dir_not_exists(self):
        DIRPATH = '/DIR'

        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)
        cacheManagerMock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cacheManagerMock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    def test_readdir_on_file(self):
        DIRPATH = '/DIR'

        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)
        cacheManagerMock.exists(DIRPATH).AndReturn(True)
        cacheManagerMock.isDirectory(DIRPATH).AndReturn(False)
        mox.Replay(cacheManagerMock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    def test_opendir_success(self):
        DIRPATH = '/DIR'

        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)
        cacheManagerMock.exists(DIRPATH).AndReturn(True)
        cacheManagerMock.isDirectory(DIRPATH).AndReturn(True)
        mox.Replay(cacheManagerMock)

        self.assertEqual(None, self.sut.opendir(DIRPATH))

    def test_opendir_not_dir(self):
        FILEPATH = '/FILE'

        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)
        cacheManagerMock.exists(FILEPATH).AndReturn(True)
        cacheManagerMock.isDirectory(FILEPATH).AndReturn(False)
        mox.Replay(cacheManagerMock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(FILEPATH))

    def test_opendir_path_not_exists(self):
        DIRPATH = '/DIR'

        cacheManagerMock = self.sut.cacheManager = mox.MockObject(cachefs.CacheManager)
        cacheManagerMock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cacheManagerMock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(DIRPATH))


