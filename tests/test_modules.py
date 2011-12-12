import sys

# to make all modules from one directory up visible
sys.path.append("../")

import shutil
import os
import subprocess
import time
import tempfile
import stat
import errno
import logging

import unittest
import mox
import pdb

import fuse
import config
import test_config
import cachefs
import mounter
from mocks.events import FilesystemEvent
from mocks.commport import InPort
import mocks.time_mock
from test_helper import TestHelper
import disk_cache
import path_factory

class ModuleTestCase(unittest.TestCase):

    def __init__(self, *args, **kw):
        unittest.TestCase.__init__(self, *args, **kw)
        self.__test_dir = None

    def setUp(self):
        cfg = TestHelper.get_cfg()
        tests_root = cfg.ut_tests_root
        testcase_current = cfg.ut_current_tc
        tc_wdir = self.__test_dir = os.sep.join([tests_root, self.__class__.__name__])
        os.makedirs(tc_wdir)
        if (os.path.lexists(testcase_current)):
            os.unlink(testcase_current)
        os.symlink(tc_wdir, testcase_current)
        TestHelper.create_source_dir(cfg.cache_manager)

        return self.setUpImpl()

    def tearDown(self):
        ret = self.tearDownImpl()
        self.cleanupWorkspace()
        return ret

    def cleanupWorkspace(self):
        self.cleanupWorkspaceImpl()
        shutil.rmtree(self.__test_dir)
        cfg = TestHelper.get_cfg()
        os.remove(cfg.ut_current_tc)

    def tearDownImpl():
        pass

    def cleanupWorkspaceImpl(self):
        pass

class CacheManagerModuleTest(ModuleTestCase):

    def setUpImpl(self):
        cachefs.memory_cache.time = time
        self.cfg = TestHelper.get_cfg()
        self.sut = cachefs.CacheManager(self.cfg.cache_manager)

    def tearDownImpl(self):
        pass

    def cleanupWorkspaceImpl(self):
        TestHelper.remove_source_dir(self.cfg.cache_manager)
        shutil.rmtree(self.sut._cfg.cache_root_dir)

class CreateCacheDir(CacheManagerModuleTest):

    def test(self):
        self.assertTrue(os.path.exists(self.sut._cfg.cache_root_dir))

class Exists(CacheManagerModuleTest):

    def test(self):
        file_path = '/TestCacheManager.test_exists.txt'
        TestHelper.create_source_file(self.cfg.cache_manager,
                                      file_path,
                                      '.' * 5)
        self.assertTrue(self.sut.isExisting(file_path))

class ExistsRoot(CacheManagerModuleTest):

    def test(self):
        file_path = '/'
        self.assertTrue(self.sut.isExisting(file_path))

class IsDir(CacheManagerModuleTest):

    def test(self):
        dir_path = '/TestCacheManager.test_isDirectory'
        TestHelper.create_source_dir(self.cfg.cache_manager, dir_path)
        self.assertTrue(self.sut.isExisting(dir_path))
        self.assertTrue(self.sut.isDirectory(dir_path))

class ListDir(CacheManagerModuleTest):
    def test(self):
        dir_path = "/TestCacheManager.test_listDir"
        cfg = self.cfg.cache_manager
        TestHelper.create_source_dir(cfg, dir_path)

        subdir_name = 'subdir'
        dir_path2 = os.sep.join([dir_path, subdir_name])
        TestHelper.create_source_dir(cfg, dir_path2)

        file_name = '1.txt'
        file_path = os.sep.join([dir_path, file_name])
        TestHelper.create_source_file(cfg, file_path, 'file_content ... ')

        self.assertTrue(self.sut.isExisting(dir_path))
        #precond:
        self.sut.getAttributes(dir_path)

        listDir_out = self.sut.listDirectory(dir_path)

        input = [file_name, subdir_name]
        self.assertEqual(sorted(input), sorted(listDir_out))

        cache_root_path = self.sut._cfg.cache_root_dir
        cache_dir_walker = disk_cache.CachedDirWalker(cache_root_path)
        path_transformer = path_factory.PathTransformer()

        cached_subdir_path = os.sep.join(
            [cache_root_path, dir_path, path_transformer.transformDirpath(subdir_name)])

        self.assertTrue(os.path.exists(cached_subdir_path))

        cached_file_path = os.sep.join(
            [cache_root_path, path_transformer.transformFilepath(file_name)])

        self.assertFalse(os.path.exists(cached_file_path))


class Getattr(CacheManagerModuleTest):
    def test(self):
        self.sut.getAttributes('.')

class CachefsSystemTest(ModuleTestCase):

    def __init__(self, *args, **kw):
        try:
            cache_via_memfs = kw['cache_via_memfs']
            del kw['cache_via_memfs']
        except KeyError:
            cache_via_memfs = False

        try:
            source_via_memfs = kw['source_via_memfs']
            del kw['source_via_memfs']
        except KeyError:
            source_via_memfs = False

        ModuleTestCase.__init__(self, *args, **kw)
        self.cfg = TestHelper.get_cfg()
        self.tag = 0 # used for testcases with reboot scenario
        self.cache_memfs = cache_via_memfs
        self.source_memfs = source_via_memfs
        if self.cache_memfs:
            self.cache_memfs_inport = None # must be initialized after port creation in test suite
            self.cache_memfs_mounter = None

        if self.source_memfs:
            self.source_memfs_inport = None # must be initialized after port creation in test suite
            self.source_memfs_mounter = None

    def setUpImpl(self):
        cfg = self.cfg 
        mountpoint = cfg.cache_fs.cache_fs_mountpoint
        self.assertTrue(not os.path.ismount(mountpoint), msg=mountpoint)
        if not os.path.exists(mountpoint):
            os.makedirs(mountpoint)

        self.prepareSource()
        self.precondition()
        self.prepareCache()

        self.mount_cachefs();

    def tearDownImpl(self):
        self.cachefs_mounter.unmount()

    def cleanupWorkspaceImpl(self):
        self.cleanupCache()
        self.cleanupSource() # TODO: consider method reordering
        #TestHelper.remove_source_dir(self.cfg.cache_manager)

    def precondition(self):
        pass

    def prepareCache(self):
        os.makedirs(self.cfg.cache_manager.cache_root_dir)
        if self.cache_memfs:
            self._mount_cache()

    def prepareSource(self):
        #TestHelper.create_source_dir(self.cfg.cache_manager)
        if self.source_memfs:
            self._mount_source()

    def cleanupCache(self):
        if self.cache_memfs:
            self.cache_memfs_mounter.unmount()
            self.cache_memfs_inport.dispose()
        # add some safety checks
        assert(self.cfg.cache_manager.cache_root_dir)
        shutil.rmtree(self.cfg.cache_manager.cache_root_dir)

    def cleanupSource(self):
        if self.source_memfs:
            self.source_memfs_mounter.unmount()
            self.source_memfs_inport.dispose()
        assert(self.cfg.cache_manager.source_dir)
        shutil.rmtree(self.cfg.cache_manager.source_dir)

    def _getstat(self, path):
        return os.lstat(self._abspath(path))

    def _listdir(self, path):
        return os.listdir(self._abspath(path))

    def _opendir(self, path):
        return os.opendir(self._abspath(path))

    def _open(self, path):
        return open(self._abspath(path))

    def _readlink(self, path):
        return os.readlink(self._abspath(path))

    def _access(self, path, mode=os.F_OK):
        return os.access(self._abspath(path), mode)

    def _abspath(self, path):
        return os.sep.join([self.cfg.cache_fs.cache_fs_mountpoint, path])


    def _mount_cache(self):

        print("Mounting Memfs for cache")

        mountId = 'cache'
        logpath = self._buildMemfsLogPath(mountId)
        unixAddr = self._buildMemfsUnixAddress(mountId)

        self.cache_memfs_inport = InPort(unixAddr)
        self.cache_memfs_inport.listen()

        cmdline_options = self._buildCmdLineOptions(self.cfg.cache_manager.cache_root_dir, logpath, unixAddr)
        self.cache_memfs_mounter = mounter.FuseFsMounter(cmdline_options)
        self.cache_memfs_mounter.mount()

    def _mount_source(self):

        print("Mounting Memfs for source")

        mountId = 'source'
        logpath = self._buildMemfsLogPath(mountId)
        unixAddr = self._buildMemfsUnixAddress(mountId)

        self.source_memfs_inport = InPort(unixAddr)
        self.source_memfs_inport.listen()

        cmdline_options = self._buildCmdLineOptions(self.cfg.cache_manager.source_dir, logpath, unixAddr)
        self.source_memfs_mounter = mounter.FuseFsMounter(cmdline_options)
        self.source_memfs_mounter.mount()

    def _buildCmdLineOptions(self, mountpoint, logpath, unixAddr):
        cmdline_options = [
            os.path.join(config.getProjectRoot(), 'tests', 'mocks', 'memfs.py'),
            mountpoint,
            '--log={log_path}'.format(log_path=logpath),
            '--commport={commport}'.format(commport=unixAddr),
            '-f' # foreground
        ]
        return cmdline_options

    def _buildMemfsLogPath(self, label):
        filename = ''.join(["LOG_MEMFS_", label, "_", self.__class__.__name__, str(self.tag), ".txt"])
        return os.path.join(self.cfg.ut_tests_root, filename)

    def _buildMemfsUnixAddress(self, label):
        filename = ''.join([label.capitalize(), self.__class__.__name__, str(self.tag), '.sock'])
        return os.path.join(self.cfg.ut_tests_root, filename)

    def mount_cachefs(self):
        cmdline_options = [
            os.path.join(config.getProjectRoot(), 'scripts', 'coverage.sh'),
            os.path.join(config.getProjectRoot(), 'cachefs.py'),
            self.cfg.cache_fs.cache_fs_mountpoint,
            '--source-dir={source}'.format(source=self.cfg.cache_manager.source_dir),
            '--cache-dir={cache}'.format(cache=self.cfg.cache_manager.cache_root_dir),
            '--log={log_path}'.format(log_path=os.path.join(self.cfg.ut_tests_root, "LOG_" + self.__class__.__name__ + str(self.tag))),
            '--disk-cache-lifetime={disk_cache_lifetime}'.format(disk_cache_lifetime=self.cfg.cache_manager.disk_cache_lifetime),
            '--memory-cache-lifetime={memory_cache_lifetime}'.format(memory_cache_lifetime=self.cfg.cache_manager.memory_cache_lifetime),
            '--debug',
            '-f' # foreground
        ]
        self.cachefs_mounter = mounter.FuseFsMounter(cmdline_options, self.cfg.cache_fs.cache_fs_mountpoint)
        try:
            self.cachefs_mounter.mount()
        except:
            print("************************************************")
            print("************************************************")
            print("CANNOT MOUNT CACHEFS, TRYING TO CLEANUP THE MESS")
            print("************************************************")
            print("************************************************")
            self.cleanupWorkspace()

class TestDirectoriesOnly(CachefsSystemTest):

    SUBDIR_1 = 'subdir1'
    SUBDIR_2 = 'subdir2'
    SUB_SUBDIR_2 = 'subdir2.1'

    def precondition(self):
        cfg = self.cfg.cache_manager
        TestHelper.create_source_dir(cfg, TestDirectoriesOnly.SUBDIR_1)
        TestHelper.create_source_dir(cfg, TestDirectoriesOnly.SUBDIR_2)
        TestHelper.create_source_dir(cfg,
                                     os.sep.join([TestDirectoriesOnly.SUBDIR_2,
                                                  TestDirectoriesOnly.SUB_SUBDIR_2]))

    def test(self):
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        path, dirs, files = os.walk(mountpoint).next()
        self.assertEqual(2, len(dirs))
        self.assertEqual(0, len(files))
        self.assertTrue(TestDirectoriesOnly.SUBDIR_1 in dirs)
        self.assertTrue(TestDirectoriesOnly.SUBDIR_2 in dirs)

        cache_root = self.cfg.cache_manager.cache_root_dir

        subdir2_path = os.sep.join([mountpoint, TestDirectoriesOnly.SUBDIR_2])
        path, dirs, files = os.walk(subdir2_path).next()
        self.assertEqual(1, len(dirs))
        self.assertEqual(0, len(files))
        self.assertEqual(sorted([TestDirectoriesOnly.SUB_SUBDIR_2]), sorted(dirs))

        sub_subdir2_path = os.sep.join([mountpoint,
                                        TestDirectoriesOnly.SUBDIR_2,
                                        TestDirectoriesOnly.SUB_SUBDIR_2])
        path, dirs, files = os.walk(sub_subdir2_path).next()
        self.assertEqual(0, len(dirs))
        self.assertEqual(0, len(files))

class TestDirectoriesAndFiles(CachefsSystemTest):

    SUBDIR_1 = 'subdir1'
    FILE_1 = 'file1'
    FILE_1_CONTENT = 'file1 content'

    FILE_2 = 'file2'
    FILE_2_SUBPATH = os.sep.join([SUBDIR_1, FILE_2])
    FILE_2_CONTENT = 'file2 content'

    def precondition(self):
        #sshcfg = self.cfg.ssh
        cls = TestDirectoriesAndFiles
        cfg = self.cfg.cache_manager
        TestHelper.create_source_file(cfg, cls.FILE_1, cls.FILE_1_CONTENT)
        TestHelper.create_source_dir(cfg, cls.SUBDIR_1)
        TestHelper.create_source_file(cfg, cls.FILE_2_SUBPATH, cls.FILE_2_CONTENT)

    def test(self):
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        path, dirs, files = os.walk(mountpoint).next()

        cls = TestDirectoriesAndFiles

        self.assertEqual(1, len(dirs))
        self.assertEqual(cls.SUBDIR_1, dirs[0])

        self.assertEqual(1, len(files))
        self.assertEqual(cls.FILE_1, files[0])

        file1_path = os.sep.join([mountpoint, files[0]])
        self.assertTrue(os.path.exists(file1_path))
        file = open(file1_path)
        read_content = file.read()
        file.close()
        self.assertEqual(cls.FILE_1_CONTENT, read_content)

class TestBigFilesWithContent(CachefsSystemTest):

    FILE_CONTENT = ''
    FILE_PATH = '/bigfile'
    FILE_SIZE = 2**24 # 16 Mb

    def precondition(self):
        cls = TestBigFilesWithContent
        cls.FILE_CONTENT = ":-)" * cls.FILE_SIZE  # 3 * 16Mb
        TestHelper.create_source_file(self.cfg.cache_manager,
                                      cls.FILE_PATH,
                                      cls.FILE_CONTENT)

    def test(self):
        cls = TestBigFilesWithContent
        f = self._open(cls.FILE_PATH)
        content = f.read()
        self.assertEqual(content, cls.FILE_CONTENT)

    def tearDownImpl(self):
        CachefsSystemTest.tearDownImpl(self)
        TestBigFilesWithContent.FILE_CONTENT = None


class RelativePaths(CachefsSystemTest):

    SUBDIR = 'subdir'
    FILE = 'file'
    FILE_CONTENT = 'content'

    SUBDIR_2 = 'subdir/subdir2'
    FILE_2 = 'subdir/subdir2/file2'
    FILE_CONTENT_2 = 'content2'

    SUBDIR_3 = 'subdir/subdir2/subdir3'
    FILE_3 = 'subdir/subdir2/subdir3/file3'
    FILE_CONTENT_3 = 'content3'

    def precondition(self):
        cfg = self.cfg.cache_manager
        cls = RelativePaths
        TestHelper.create_source_dir(cfg, cls.SUBDIR)
        TestHelper.create_source_file(cfg, cls.FILE, cls.FILE_CONTENT)

        TestHelper.create_source_dir(cfg, cls.SUBDIR_2)
        TestHelper.create_source_file(cfg, cls.FILE_2, cls.FILE_CONTENT_2)

        TestHelper.create_source_dir(cfg, cls.SUBDIR_3)
        TestHelper.create_source_file(cfg, cls.FILE_3, cls.FILE_CONTENT_3)

    def test(self):
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        cls = RelativePaths

        normalized_filepath = os.sep.join([mountpoint, 'file'])
        self.assertTrue(os.path.lexists(normalized_filepath))
        self.assertEqual(cls.FILE_CONTENT, open(normalized_filepath).read())

        FILE_RELATIVE = 'subdir/subdir2/subdir3/../../../file'
        filepath = os.sep.join([mountpoint, FILE_RELATIVE])
        self.assertTrue(os.path.lexists(filepath))
        self.assertEqual(cls.FILE_CONTENT, open(filepath).read())

        FILE2_RELATIVE = 'subdir/./subdir2/subdir3/../file2'
        filepath2 = os.sep.join([mountpoint, FILE2_RELATIVE])
        self.assertTrue(os.path.lexists(filepath2))
        self.assertEqual(cls.FILE_CONTENT_2, open(filepath2).read())

class GetattrFs(CachefsSystemTest):

    permissions = [  0444, 0777, 0700, 07777, 04444 ]

    def precondition(self):
        def create_file(permissions):
            TestHelper.execute_source(self.cfg, '''
                    touch {pmss:o}
                    chmod {pmss:o} {pmss:o}
            '''.format(pmss = permissions)) # x:o - i.e. x converted to oct format

        def create_dir(permissions):
            TestHelper.execute_source(self.cfg, '''
                    mkdir {pmss:o}_dir
                    chmod {pmss:o} {pmss:o}_dir
            '''.format(pmss = permissions)) # x:o - i.e. x converted to oct format

        for item in GetattrFs.permissions:
            create_file(item)
            create_dir(item)

    def cleanupWorkspaceImpl(self):
        # additional task to have permission to cleanup 
        TestHelper.execute_source(self.cfg, '''
                chmod +rwx -R .
                ''')
        CachefsSystemTest.cleanupWorkspaceImpl(self)

    def test(self):
        def getstat(path):
            full_path = os.sep.join([self.cfg.cache_fs.cache_fs_mountpoint, path])
            return os.lstat(full_path)

        def check(permission):
            st = getstat("{path:o}".format(path=permission))
            s_format = "permission(=0{permission:o}) & st_mode(=0{st_mode:o}) != permission(=0{merge:o}) for file with name (sic!) 0{permission:o}"
            self.assertEqual(permission, st.st_mode & 07777, 
                s_format.format(permission=permission, st_mode=st.st_mode & 07777, merge=permission & st.st_mode))

        def check_dir(permission):
            st = getstat("{path:o}_dir".format(path=permission))
            s_format = "permission(=0{permission:o}) & st_mode(=0{st_mode:o}) != permission(=0{merge:o}) for file with name (sic!) 0{permission:o}"
            self.assertEqual(permission, st.st_mode & 07777, 
                s_format.format(permission=permission, st_mode=st.st_mode & 07777, merge=permission & st.st_mode))

        for item in GetattrFs.permissions:
            check(item)
            check_dir(item)

class SymbolicLinks(CachefsSystemTest):

    def precondition(self):
        TestHelper.execute_source(self.cfg, '''
            mkdir -p a/b/c

            mkdir -p e/f/g
            touch e/f/g/1.txt

            mkdir -p i/f/g
            touch i/f/g/2.txt

            ln -s ../../../i/f/g e/f/g/j
            ln -s a b
            ln -s ../../../i/f/g/2.txt e/f/g/link_to_e
            ''')

    def test(self):
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint

        full_path = os.sep.join([mountpoint, 'a/b/c'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isdir(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isdir(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/1.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))

        full_path = os.sep.join([mountpoint, 'i/f/g/2.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j'])
        self.assertTrue(os.path.exists(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j/2.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j/1.txt'])
        self.assertFalse(os.path.exists(full_path))

        full_path = os.sep.join([mountpoint, 'b'])
        self.assertTrue(os.path.lexists(full_path))
        self.assertTrue(os.path.islink(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/link_to_e'])
        self.assertTrue(os.path.lexists(full_path))
        self.assertTrue(os.path.islink(full_path))
        self.assertTrue(os.path.exists(full_path))

class CachefsSystemTestAfterReboot(CachefsSystemTest):

    class DummyTest(object):
        def precondition(self):
            pass

        def test(self):
            pass

        def tearDown(self):
            pass

        def setUp(self):
            pass

    def __init__(self, *args, **kw):
        CachefsSystemTest.__init__(self, *args, **kw)
        self._test = CachefsSystemTestAfterReboot.DummyTest()

    def initialize(self, test):
        self._test = test

    def _restart_cachefs(self):
        self.cachefs_mounter.unmount()
        self.tag += 1 # for another log creation
        self.mount_cachefs()

    def precondition(self):
        self._test.precondition()

    '''
    def cleanupWorkspace(self):
        self._test.cleanupWorkspace()
        CachefsSystemTest.cleanupWorkspace(self)

    def tearDownImpl(self):
        self._test.tearDownImpl()
        CachefsSystemTest.tearDownImpl(self)
    '''

    def test(self):
        cachefs.DEBUG("Test Setup")
        #self._test.setUp()
        cachefs.DEBUG("Initial Test")
        self._test.test()
        cachefs.DEBUG("Restart CacheFs")
        self._restart_cachefs()
        cachefs.DEBUG("Repeat the test after CacheFs restart")
        self._test.test()
        cachefs.DEBUG("Test TearDown")
        #self._test.tearDown()


class TestDirectoriesOnlyAfterReboot(CachefsSystemTestAfterReboot):

    def __init__(self, *args, **kw):
        CachefsSystemTestAfterReboot.__init__(self, *args, **kw)
        tc = TestDirectoriesOnly(*args, **kw)
        self.initialize(tc)

class TestDirectoriesAndFilesAfterReboot(CachefsSystemTestAfterReboot):

    def __init__(self, *args, **kw):
        CachefsSystemTestAfterReboot.__init__(self, *args, **kw)
        tc = TestDirectoriesAndFiles(*args, **kw)
        self.initialize(tc)

class TestRelativePathsAfterReboot(CachefsSystemTestAfterReboot):

    def __init__(self, *args, **kw):
        CachefsSystemTestAfterReboot.__init__(self, *args, **kw)
        tc = RelativePaths(*args, **kw)
        self.initialize(tc)

class TestGetattrFsAfterReboot(CachefsSystemTestAfterReboot):

    def __init__(self, *args, **kw):
        CachefsSystemTestAfterReboot.__init__(self, *args, **kw)
        tc = GetattrFs(*args, **kw)
        self.initialize(tc)

class TestSymbolicLinksAfterReboot(CachefsSystemTestAfterReboot):

    def __init__(self, *args, **kw):
        CachefsSystemTestAfterReboot.__init__(self, *args, **kw)
        tc = SymbolicLinks(*args, **kw)
        self.initialize(tc)

class TestSymoblicLinksAfterRebootWithMemfs(TestSymbolicLinksAfterReboot):

    def __init__(self, *args, **kw):
        TestSymbolicLinksAfterReboot.__init__(self, *args, cache_via_memfs=True, source_via_memfs=True, **kw)

class TestAccessToCacheAndSourceDirectories(CachefsSystemTest):

    def __init__(self, *args, **kw):
        CachefsSystemTest.__init__(self, *args, cache_via_memfs=True, source_via_memfs=True, **kw)

    def precondition(self):
        TestHelper.execute_source(self.cfg, '''
            mkdir i
            echo 'dummy content' >> i/2.txt
            chmod ugo+rwx i/2.txt
            ln -s i/2.txt 2.txt
            ''')

    def test(self):

        self.maxDiff = None

        def cacheableOperations():
            self._access("/NON_EXISTING_FILE", os.F_OK)
            self._getstat("/i/2.txt")
            self._getstat("/2.txt")
            self._readlink("/2.txt")
            try:
                self._readlink("/23.txt")
            except OSError, e:
                pass
            self._access("/i/2.txt", os.R_OK)
            self._access("/i/2.txt", os.W_OK)
            self._access("/i/2.txt", os.X_OK)
            try:
                self._listdir("/i/2.txt")
            except OSError, e:
                pass

            self._listdir("/i")
            self._listdir("/")

        cacheableOperations()

        time.sleep(0.5)

        TestHelper.fetch_all(self.source_memfs_inport)
        TestHelper.fetch_all(self.cache_memfs_inport)

        cacheableOperations()

        time.sleep(0.5)

        source_check = TestHelper.fetch_all(self.source_memfs_inport)
        self.assertEqual([], source_check)

        cache_check = TestHelper.fetch_all(self.cache_memfs_inport)
        self.assertEqual([], cache_check)


class CacheFsWithMockedTimerTestCase(CachefsSystemTest):

    def __init__(self, *args, **kw):
        CachefsSystemTest.__init__(self, *args, cache_via_memfs=True, source_via_memfs=True, **kw)
        self.moxConfig = mox.Mox()
        self.initialTimeValue = 0

    def precondition(self):
        TestHelper.execute_source(self.cfg, '''
            mkdir dir
            echo "Dummy content" >> dir/file
            echo "Dummy content of file 2" >> dir/file2
            ln -s dir/file link
        ''')

    def mount_cachefs(self):
        self.timeModule = mocks.time_mock.ModuleInterface()
        self.timeController = self.timeModule.getController()

        self.moxConfig.StubOutWithMock(self.timeController, "_timeImpl")
        self.timeController._timeImpl().MultipleTimes().AndReturn(self.initialTimeValue)
        self.moxConfig.ReplayAll()

        os.symlink(os.path.join(config.getProjectRoot(), 'tests', 'mocks'), 
                   os.path.join(config.getProjectRoot(), 'mocks'))
        CachefsSystemTest.mount_cachefs(self)

        TestHelper.fetch_all(self.source_memfs_inport)
        TestHelper.fetch_all(self.cache_memfs_inport)


    def tearDownImpl(self):
        CachefsSystemTest.tearDownImpl(self)
        os.remove(os.path.join(config.getProjectRoot(), 'mocks'))
        self.timeController.finalize()
        self.timeController.dispose()
        self.timeModule.server.join()
        self.moxConfig.UnsetStubs()

    def test(self):
        pass
        '''
        #self.moxConfig.UnsetStubs() # seems to be unnecessary
        self.moxConfig.ResetAll()
        #self.moxConfig.StubOutWithMock(self.timeController, "time") # seems to be unnecessary
        self.timeController.time().MultipleTimes().AndReturn(19)
        self.moxConfig.ReplayAll()

        self._getstat("/dir")
        self._getstat("/dir/file")
        '''

class locked(object):

    def __init__(self, lockable):
        self._lockable = lockable

    def __enter__(self):
        self._lockable.lock()

    def __exit__(self, type, value, traceback):
        self._lockable.unlock()

    def __getattr__(self, item):
        if hasattr(self.lockable, item):
            return getattr(self.lockable, item)
        return getattr(self, item)


class MemoryCacheExpiration(CacheFsWithMockedTimerTestCase):

    def test(self):
        self.maxDiff = None

        st = self._getstat("/dir/file")
        self.assertNotEqual([], TestHelper.fetch_all(self.source_memfs_inport))
        self.assertNotEqual([], TestHelper.fetch_all(self.cache_memfs_inport))

        self.assertEqual(st, self._getstat("/dir/file"))
        self.assertEqual([], TestHelper.fetch_all(self.source_memfs_inport))
        self.assertEqual([], TestHelper.fetch_all(self.cache_memfs_inport))

        f = self._open("/dir/file")
        f.readlines()
        f.close()

        self.assertNotEqual([], TestHelper.fetch_all(self.source_memfs_inport))
        self.assertNotEqual([], TestHelper.fetch_all(self.cache_memfs_inport))

        time.sleep(0.5)

        with locked(self.timeController):
            self.moxConfig.UnsetStubs()
            self.moxConfig.StubOutWithMock(self.timeController, "_timeImpl")
            newTime = self.initialTimeValue + self.cfg.cache_manager.memory_cache_lifetime + 1
            self.assertTrue(newTime - self.initialTimeValue < self.cfg.cache_manager.disk_cache_lifetime)
            self.timeController._timeImpl().MultipleTimes().AndReturn(newTime)
            self.moxConfig.ReplayAll()

        self._getstat("/dir/file")

        self.assertEqual([], TestHelper.fetch_all(self.source_memfs_inport))
        self.assertNotEqual([], TestHelper.fetch_all(self.cache_memfs_inport))

        dirlist = self._listdir("/dir")
        self.assertEqual(set(['file', 'file2']), set(dirlist))

        self.assertEqual([], TestHelper.fetch_all(self.source_memfs_inport))
        self.assertNotEqual([], TestHelper.fetch_all(self.cache_memfs_inport))

class DiscCacheExpiration(CacheFsWithMockedTimerTestCase):

    def test(self):
        self.maxDiff = None

        self._getstat("/dir/file")
        self.assertNotEqual([], TestHelper.fetch_all(self.source_memfs_inport))

        self._getstat("/")
        self._getstat("/dir")
        self._getstat("/dir/file")
        self.assertEqual([], TestHelper.fetch_all(self.source_memfs_inport))

        # TODO
        '''
        # move time forward to trigger time expiration
        self.moxConfig.ResetAll()
        newTime = self.initialTimeValue + self.cfg.cache_manager.disk_cache_lifetime + 1
        self.timeController.time().MultipleTimes().AndReturn(newTime)
        self.moxConfig.ReplayAll()

        self._getstat("/dir/file")
        self.assertNotEqual([], TestHelper.fetch_all(self.source_memfs_inport))
        '''
