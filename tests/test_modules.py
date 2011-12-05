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
from mocks.commport import InPort
import mocks.time_mock

#sys.path.remove("../")

def logger_tm(f):
    def wrapper(*args, **kw):
        class_name = args[0].__class__.__name__
        func_name = f.func_name
        cachefs.DEBUG("TESTCASE ---------- %s.%s ---------------" % (class_name, func_name))
        retval =  f(*args, **kw)
        cachefs.DEBUG("END OF TESTCASE ---------- %s.%s ---------------" % (class_name, func_name))
        return retval
    wrapper.func_name = f.func_name
    wrapper.__doc__ = f.__doc__
    return wrapper

class TestHelper:

    @staticmethod
    def get_cfg():
        return test_config.getConfig()

    @staticmethod
    def create_source_dir(cfg, path = ''):
        if path:
            source_dir = os.sep.join([cfg.source_dir, path])
        else:
            source_dir = cfg.source_dir
        os.makedirs(source_dir)

    @staticmethod
    def remove_source_dir(cfg, path = ''):
        assert(cfg.source_dir)
        if path:
            source_dir = os.path.join(cfg.source_dir, path)
        else:
            source_dir = cfg.source_dir
        shutil.rmtree(source_dir)

    @staticmethod
    def remove_source_file(cfg, subpath):
        source_path = os.sep.join([cfg.source_dir, subpath])
        os.unlink(source_path)

    @staticmethod
    def create_source_file(cfg, subpath, content = ''):
        source_path = os.sep.join([cfg.source_dir, subpath])
        f = open(source_path, 'w')
        f.write(content)
        f.close()

    @staticmethod
    def execute_source(cfg, script):
        cwd = os.getcwd()
        os.chdir(cfg.cache_manager.source_dir)
        named_tmp_file = tempfile.NamedTemporaryFile('wx+b')
        named_tmp_file.write(script)
        named_tmp_file.flush()
        TMP_BIN = '/tmp/tmp_bin'
        shutil.copyfile(named_tmp_file.name, TMP_BIN)
        os.chmod(TMP_BIN, 0777)
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call([TMP_BIN], shell = True, stdout = fnull))
        os.unlink(TMP_BIN)
        os.chdir(cwd)

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

class CacheFsUnitTest(unittest.TestCase):

    def setUp(self):
        self.sut = cachefs.CacheFs()
        self.sut.cfg = TestHelper.get_cfg()

    def tearDown(self):
        pass

    def test_access(self):
        # inject mock
        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)

        # setup mock
        cache_mgr_mock.exists('file1').AndReturn(True)
        cache_mgr_mock.exists('file2').AndReturn(False)
        cache_mgr_mock.exists('file3').AndReturn(True)
        mox.Replay(cache_mgr_mock)

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

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(True)
        cache_mgr_mock.list_dir(DIRPATH).AndReturn(dir_entries)
        mox.Replay(cache_mgr_mock)

        dir_entries_match = dir_entries + ['.', '..']
        readdir_entries = []

        for entry in self.sut.readdir(DIRPATH, 0, ''):
            self.assertTrue(isinstance(entry, fuse.Direntry))
            self.assertTrue(entry.name in dir_entries_match)
            readdir_entries.append(entry.name)

        self.assertEqual(sorted(dir_entries_match), sorted(readdir_entries))

    def test_readdir_dir_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    def test_readdir_on_file(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    def test_opendir_success(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock._has_init_stamp(DIRPATH).AndReturn(False)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(True)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.opendir(DIRPATH))

    def test_opendir_not_dir(self):
        FILEPATH = '/FILE'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock._has_init_stamp(FILEPATH).AndReturn(False)
        cache_mgr_mock.exists(FILEPATH).AndReturn(True)
        cache_mgr_mock.is_dir(FILEPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(FILEPATH))

    def test_opendir_path_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock._has_init_stamp(DIRPATH).AndReturn(False)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(DIRPATH))

    def test_memcache_get_attributes(self):
        memcache = cachefs.MemoryCache()

        root_path = "/"
        root_stat = 54321
        self.assertEqual(None, memcache.get_attributes(root_path))
        memcache.cache_attributes(root_path, root_stat)
        self.assertEqual(root_stat, memcache.get_attributes(root_path).stat)

        some_stat = 12345
        some_path = "/example/file"
        self.assertEqual(None, memcache.get_attributes(some_path))
        memcache.cache_attributes(some_path, some_stat)
        self.assertEqual(some_stat, memcache.get_attributes(some_path).stat)

    def test_memcache_cache_link_target(self):
        memcache = cachefs.MemoryCache()
        some_target = "target"
        some_path = "/example/link"
        self.assertEqual(None, memcache.read_link(some_path))
        memcache.cache_link_target(some_path, some_target)
        self.assertEqual(some_target, memcache.read_link(some_path).target)

    def test_memcache_save_stamp(self):
        memcache = cachefs.MemoryCache()
        some_path = "/example/dir"
        self.assertFalse(memcache.has_stamp(some_path))
        memcache.save_stamp(some_path)
        self.assertTrue(memcache.has_stamp(some_path))

    def test_memcache_list_dir(self):
        memcache = cachefs.MemoryCache()
        memcache.cache_attributes('/', 1)
        memcache.cache_attributes('/home', 2)
        memcache.cache_attributes('/home/a', 3)
        memcache.cache_attributes('/home/b', 4)

        self.assertEqual(['home'], memcache.list_dir('/'))
        self.assertEqual(['a', 'b'], memcache.list_dir('/home'))

class CacheManagerModuleTest(ModuleTestCase):

    def setUpImpl(self):
        self.cfg = TestHelper.get_cfg()
        self.sut = cachefs.CacheManager(self.cfg.cache_manager)
        self.sut.run()

    def tearDownImpl(self):
        self.sut.stop()

    def cleanupWorkspaceImpl(self):
        TestHelper.remove_source_dir(self.cfg.cache_manager)
        shutil.rmtree(self.sut.cfg.cache_root_dir)

class CreateCacheDir(CacheManagerModuleTest):

    def test_create_cache_dir(self):
        self.assertTrue(os.path.exists(self.sut.cfg.cache_root_dir))

class Exists(CacheManagerModuleTest):

    def test_exists(self):
        file_path = '/TestCacheManager.test_exists.txt'
        TestHelper.create_source_file(self.cfg.cache_manager,
                                      file_path,
                                      '.' * 5)
        self.assertTrue(self.sut.exists(file_path))

class ExistsRoot(CacheManagerModuleTest):

    def test_exists_root(self):
        file_path = '/'
        self.assertTrue(self.sut.exists(file_path))

class IsDir(CacheManagerModuleTest):

    def test_is_dir(self):
        '''CacheManagerModuleTest: is directory'''
        dir_path = '/TestCacheManager.test_is_dir'
        TestHelper.create_source_dir(self.cfg.cache_manager, dir_path)
        self.assertTrue(self.sut.exists(dir_path))
        self.assertTrue(self.sut.is_dir(dir_path))

class ListDir(CacheManagerModuleTest):
    def test_list_dir(self):
        '''CacheManagerModuleTest: list directories'''
        dir_path = "/TestCacheManager.test_list_dir"
        cfg = self.cfg.cache_manager
        TestHelper.create_source_dir(cfg, dir_path)

        subdir_name = 'subdir'
        dir_path2 = os.sep.join([dir_path, subdir_name])
        TestHelper.create_source_dir(cfg, dir_path2)

        file_name = '1.txt'
        file_path = os.sep.join([dir_path, file_name])
        TestHelper.create_source_file(cfg, file_path, 'file_content ... ')

        self.assertTrue(self.sut.exists(dir_path))
        #precond:
        self.sut.get_attributes(dir_path)

        list_dir_out = self.sut.list_dir(dir_path)
        self.assertTrue(self.sut._has_init_stamp(dir_path))

        input = [file_name, subdir_name]
        self.assertEqual(sorted(input), sorted(list_dir_out))

        cache_root_path = self.sut.cfg.cache_root_dir
        cache_dir_walker = cachefs.CacheManager.CachedDirWalker(cache_root_path)
        path_transformer = cachefs.CacheManager.PathTransformer()

        cached_subdir_path = os.sep.join(
            [cache_root_path, dir_path, path_transformer.transform_dirpath(subdir_name)])

        self.assertTrue(os.path.exists(cached_subdir_path))

        cached_file_path = os.sep.join(
            [cache_root_path, path_transformer.transform_filepath(file_name)])

        self.assertFalse(os.path.exists(cached_file_path))


class Getattr(CacheManagerModuleTest):
    def test(self):
        self.sut.get_attributes('.')

class CacheFsModuleTest(ModuleTestCase):

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


    def _readlink(self, path):
        return os.readlink(self._abspath(path))

    def _access(self, path, mode):
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
            os.path.join(config.getProjectRoot(), 'cachefs.py'),
            self.cfg.cache_fs.cache_fs_mountpoint,
            '--source-dir={source}'.format(source=self.cfg.cache_manager.source_dir),
            '--cache-dir={cache}'.format(cache=self.cfg.cache_manager.cache_root_dir),
            '--log={log_path}'.format(log_path=os.path.join(self.cfg.ut_tests_root, "LOG_" + self.__class__.__name__ + str(self.tag))),
            '--debug',
            '-f' # foreground
        ]
        self.cachefs_mounter = mounter.FuseFsMounter(cmdline_options)
        self.cachefs_mounter.mount()

class TestDirectoriesOnly(CacheFsModuleTest):

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
        '''App test: directories'''
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

class TestDirectoriesAndFiles(CacheFsModuleTest):

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
        '''App test: Check directories and files'''
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

class RelativePaths(CacheFsModuleTest):

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
        '''App test: Relative paths'''

        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        cls = RelativePaths

        normalized_filepath = os.sep.join([mountpoint, 'file'])
        self.assertTrue(os.path.lexists(normalized_filepath))
        self.assertEqual(cls.FILE_CONTENT, open(normalized_filepath).read())

        FILE_RELATIVE = 'subdir/subdir2/subdir3/../../../file'
        rel_filepath = os.sep.join([mountpoint, FILE_RELATIVE])
        self.assertTrue(os.path.lexists(rel_filepath))
        self.assertEqual(cls.FILE_CONTENT, open(rel_filepath).read())

        FILE2_RELATIVE = 'subdir/./subdir2/subdir3/../file2'
        rel_filepath2 = os.sep.join([mountpoint, FILE2_RELATIVE])
        self.assertTrue(os.path.lexists(rel_filepath2))
        self.assertEqual(cls.FILE_CONTENT_2, open(rel_filepath2).read())

class GetattrFs(CacheFsModuleTest):

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
        cachefs.DEBUG("cleanup LALALA")
        TestHelper.execute_source(self.cfg, '''
                chmod +rwx -R .
                ''')
        CacheFsModuleTest.cleanupWorkspaceImpl(self)

    def test(self):
        '''App test: file permissions'''
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

class SymbolicLinks(CacheFsModuleTest):

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
        '''App test: Symbolic links'''
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

class CacheFsModuleTestAfterReboot(CacheFsModuleTest):

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
        CacheFsModuleTest.__init__(self, *args, **kw)
        self._test = CacheFsModuleTestAfterReboot.DummyTest()

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
        CacheFsModuleTest.cleanupWorkspace(self)

    def tearDownImpl(self):
        self._test.tearDownImpl()
        CacheFsModuleTest.tearDownImpl(self)
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


class TestDirectoriesOnlyAfterReboot(CacheFsModuleTestAfterReboot):

    def __init__(self, *args, **kw):
        CacheFsModuleTestAfterReboot.__init__(self, *args, **kw)
        tc = TestDirectoriesOnly(*args, **kw)
        self.initialize(tc)

class TestDirectoriesAndFilesAfterReboot(CacheFsModuleTestAfterReboot):

    def __init__(self, *args, **kw):
        CacheFsModuleTestAfterReboot.__init__(self, *args, **kw)
        tc = TestDirectoriesAndFiles(*args, **kw)
        self.initialize(tc)

class TestRelativePathsAfterReboot(CacheFsModuleTestAfterReboot):

    def __init__(self, *args, **kw):
        CacheFsModuleTestAfterReboot.__init__(self, *args, **kw)
        tc = RelativePaths(*args, **kw)
        self.initialize(tc)

class TestGetattrFsAfterReboot(CacheFsModuleTestAfterReboot):

    def __init__(self, *args, **kw):
        CacheFsModuleTestAfterReboot.__init__(self, *args, **kw)
        tc = GetattrFs(*args, **kw)
        self.initialize(tc)

class TestSymbolicLinksAfterReboot(CacheFsModuleTestAfterReboot):

    def __init__(self, *args, **kw):
        CacheFsModuleTestAfterReboot.__init__(self, *args, **kw)
        tc = SymbolicLinks(*args, **kw)
        self.initialize(tc)

class TestSymoblicLinksAfterRebootWithMemfs(TestSymbolicLinksAfterReboot):

    def __init__(self, *args, **kw):
        TestSymbolicLinksAfterReboot.__init__(self, *args, cache_via_memfs=True, source_via_memfs=True, **kw)

class TestWithMockTimer(CacheFsModuleTest):

    def mount_cachefs(self):
        self.timeModule = mocks.time_mock.ModuleInterface()
        self.timeController = self.timeModule.getController()
        os.symlink(os.path.join(config.getProjectRoot(), 'tests', 'mocks'), 
                   os.path.join(config.getProjectRoot(), 'mocks'))
        CacheFsModuleTest.mount_cachefs(self)

    def tearDownImpl(self):
        CacheFsModuleTest.tearDownImpl(self)
        os.remove(os.path.join(config.getProjectRoot(), 'mocks'))
        self.timeController.finalize()
        self.timeController.dispose()
        self.timeModule.server.join()

    def test(self):
        pass

class TestCacheAndSourceMocked(CacheFsModuleTest):
    '''Testcase with mocked: time, source directory, cache directory'''

    def _fetchAll(self, port):
        ret = []
        try:
            while True:
                msg = port.receive(0.01)
                ret.append(msg)
                #print(`port` + " receive: " + " " + str(msg))
        except InPort.Timeout, e:
            print("All message received from port, number: " + str(len(ret)))
            pass
        return ret

    def precondition(self):
        TestHelper.execute_source(self.cfg, '''
            mkdir i
            echo 'dummy content' >> i/2.txt
            chmod ugo+rwx i/2.txt
            ln -s i/2.txt 2.txt
            ''')


    def __init__(self, *args, **kw):
        CacheFsModuleTest.__init__(self, *args, cache_via_memfs=True, source_via_memfs=True, **kw)

    def test(self):

        def cacheableOperations():
            self._access("/NON_EXISTING_FILE", os.F_OK)
            self._getstat("/i/2.txt")
            self._getstat("/2.txt")
            self._listdir("/i")
            self._readlink("/2.txt")
            self._access("/i/2.txt", os.R_OK)
            self._access("/i/2.txt", os.W_OK)
            self._access("/i/2.txt", os.X_OK)
            self._listdir("/")


        cacheableOperations()

        self._fetchAll(self.source_memfs_inport)
        self._fetchAll(self.cache_memfs_inport)

        '''
        cache_check = map(lambda x: x[1] + x[2], cache_check)
        cache_check = dict(zip(cache_check, map(lambda x: cache_check.count(x), cache_check)))

        self.assertEqual([], filter(lambda x: x > 1, cache_check.values()), 
                "Memory cache not used in some cases, number of repetead operations:\n" 
                + str('\n'.join([str(x) for x in list(filter(lambda x: x[1] > 1, cache_check.items()))])))
        '''

        cacheableOperations()

        source_check = self._fetchAll(self.source_memfs_inport)
        self.assertEqual([], source_check)

        cache_check = self._fetchAll(self.cache_memfs_inport)
        self.assertEqual([], cache_check)
