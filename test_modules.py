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

import fuse
import config
import test_config
import sshcachefs
import runner

def logger_tm(f):
    def wrapper(*args, **kw):
        class_name = args[0].__class__.__name__
        func_name = f.func_name
        logging.debug("TESTCASE ---------- %s.%s ---------------" % (class_name, func_name))
        retval =  f(*args, **kw)
        logging.debug("END OF TESTCASE ---------- %s.%s ---------------" % (class_name, func_name))
        return retval
    wrapper.func_name = f.func_name
    return wrapper

class TestHelper:

    @staticmethod
    def get_cfg_for_test():
        return test_config.getConfig()

    @staticmethod
    def create_remote_dir(cfg, path = ''):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        if path:
            remote_dir = os.sep.join([cfg.remote_dir, path])
        else:
            remote_dir = cfg.remote_dir
        standalone_cmd = " ".join(['mkdir', '-p', remote_dir])
        user_host = "@".join([cfg.user, cfg.server])
        call_args = [cfg.ut_ssh_bin, user_host, standalone_cmd]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def remove_remote_dir(cfg, path = ''):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        if path:
            remote_dir = os.sep.join([cfg.remote_dir, path])
        else:
            remote_dir = cfg.remote_dir
        standalone_cmd = " ".join(['rm', '-rf', remote_dir])
        user_host = "@".join([cfg.user, cfg.server])
        call_args = [cfg.ut_ssh_bin, user_host, standalone_cmd]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def remove_remote_file(cfg, subpath):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        remote_file = os.sep.join([cfg.remote_dir, subpath])
        standalone_cmd = " ".join(['rm', '-rf', remote_file])
        user_host = "@".join([cfg.user, cfg.server])
        call_args = [cfg.ut_ssh_bin, user_host, standalone_cmd]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def create_remote_file(cfg, rel_path, content = ''):
        named_tmp_file = tempfile.NamedTemporaryFile()
        named_tmp_file.write(content)
        named_tmp_file.flush()
        user_host = "@".join([cfg.user, cfg.server])
        path = os.sep.join([cfg.remote_dir, rel_path])
        user_host_path = ":".join([user_host, path])
        call_args = [cfg.ut_scp_bin, named_tmp_file.name, user_host_path]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))
        named_tmp_file.close() # automatically will be removed

    @staticmethod
    def execute_remote(cfg, script):
        rel_path = 'remote_cmd.sh'
        named_tmp_file = tempfile.NamedTemporaryFile('wx+b')
        named_tmp_file.write(script)
        named_tmp_file.flush()
        os.chmod(named_tmp_file.name, 0777)
        user_host = "@".join([cfg.user, cfg.server])
        script_path = os.sep.join([cfg.remote_dir, rel_path])
        user_host_path = ":".join([user_host, script_path])
        call_args = [cfg.ut_scp_bin, named_tmp_file.name, user_host_path]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))
        named_tmp_file.close() # automatically will be removed
        # execute:
        call_args = [cfg.ut_ssh_bin, user_host, "cd %s; %s" % (cfg.remote_dir, script_path)]
        print subprocess.Popen(call_args, shell = False, stdout = subprocess.PIPE).communicate()[0]
        call_args = [cfg.ut_ssh_bin, user_host, "cd %s; rm %s" % (cfg.remote_dir, script_path)]
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

class ModuleTestCase(unittest.TestCase):

    def setUp(self):
        cfg = TestHelper.get_cfg_for_test()
        tests_root = cfg.ut_tests_root
        testcase_current = cfg.ut_current_tc
        tc_wdir = self.__test_dir = os.sep.join([tests_root, self.__class__.__name__])

        #if os.path.exists(tc_wdir):
            #shutil.rmtree(tc_wdir)
        os.makedirs(tc_wdir)
        if os.path.lexists(testcase_current):
            os.remove(testcase_current)
        os.symlink(tc_wdir, testcase_current)

        return self.setUpImpl()

    def tearDown(self):
        self.tearDownImpl()
        shutil.rmtree(self.__test_dir)
        cfg = TestHelper.get_cfg_for_test()
        os.remove(cfg.ut_current_tc)

class SshCacheFsUnitTest(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshCacheFs(TestHelper.get_cfg_for_test())

    def tearDown(self):
        pass

    @logger_tm
    def test_access(self):
        # inject mock
        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)

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

    @logger_tm
    def test_readdir(self):
        DIRPATH = '/DIR'
        dir_entries = ['file', 'subdir', 'file2']

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
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

    @logger_tm
    def test_readdir_dir_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    @logger_tm
    def test_readdir_on_file(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    @logger_tm
    def test_opendir_success(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(True)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.opendir(DIRPATH))

    @logger_tm
    def test_opendir_not_dir(self):
        FILEPATH = '/FILE'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(FILEPATH).AndReturn(True)
        cache_mgr_mock.is_dir(FILEPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(FILEPATH))

    @logger_tm
    def test_opendir_path_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(DIRPATH))

    #@logger_tm
    #def test_readlink_success(self):
        #FILEPATH = '/File'
        #CACHED_FILE_PATH = "/ABSOLUTE/PATH/TO/CACHED/FILE"

        #cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        #cache_mgr_mock.get_path_to_file(FILEPATH).AndReturn(CACHED_FILE_PATH)
        #mox.Replay(cache_mgr_mock)

        #self.assertEqual(CACHED_FILE_PATH, self.sut.readlink(FILEPATH))

    #@logger_tm
    #def test_readlink_not_found(self):
        #FILEPATH = '/File'

        #cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        #cache_mgr_mock.get_path_to_file(FILEPATH).AndReturn(None)
        #mox.Replay(cache_mgr_mock)

        #self.assertEqual(-errno.ENOENT, self.sut.readlink(FILEPATH))

class SshCacheFsModuleTest(ModuleTestCase):

    def precondition(self):
        pass

    def setUpImpl(self):
        cfg = self.cfg = TestHelper.get_cfg_for_test()
        mountpoint = cfg.cache_fs.cache_fs_mountpoint
        self.assertTrue(not os.path.ismount(mountpoint), msg=mountpoint)
        if not os.path.exists(mountpoint):
            os.makedirs(mountpoint)
        TestHelper.create_remote_dir(cfg.ssh)
        self.precondition()
        self.runner = runner.SshCacheFsRunner(test_config)
        self.runner.run()

    def tearDownImpl(self):
        self.runner.stop()
        TestHelper.remove_remote_dir(self.cfg.ssh)
        # add some safety checks
        assert(self.cfg.cache_manager.cache_root_dir)
        shutil.rmtree(self.cfg.cache_manager.cache_root_dir)

class TestDirectoriesOnly(SshCacheFsModuleTest):

    SUBDIR_1 = 'subdir1'
    SUBDIR_2 = 'subdir2'
    SUB_SUBDIR_2 = 'subdir2.1'

    def precondition(self):
        sshcfg = self.cfg.ssh
        TestHelper.create_remote_dir(sshcfg, TestDirectoriesOnly.SUBDIR_1)
        TestHelper.create_remote_dir(sshcfg, TestDirectoriesOnly.SUBDIR_2)
        TestHelper.create_remote_dir(sshcfg,
                                     os.sep.join([TestDirectoriesOnly.SUBDIR_2,
                                                  TestDirectoriesOnly.SUB_SUBDIR_2]))

    @logger_tm
    def test(self):
        '''Directories'''
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        path, dirs, files = os.walk(mountpoint).next()
        self.assertTrue(TestDirectoriesOnly.SUBDIR_1 in dirs)
        self.assertTrue(TestDirectoriesOnly.SUBDIR_2 in dirs)
        self.assertEqual(2, len(dirs))
        self.assertEqual(0, len(files))

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

class TestDirectoriesAndFiles(SshCacheFsModuleTest):

    SUBDIR_1 = 'subdir1'
    FILE_1 = 'file1'
    FILE_1_CONTENT = 'file1 content'

    FILE_2 = 'file2'
    FILE_2_SUBPATH = os.sep.join([SUBDIR_1, FILE_2])
    FILE_2_CONTENT = 'file2 content'

    def precondition(self):
        sshcfg = self.cfg.ssh
        cls = TestDirectoriesAndFiles
        TestHelper.create_remote_file(sshcfg, cls.FILE_1, cls.FILE_1_CONTENT)
        TestHelper.create_remote_dir(sshcfg, cls.SUBDIR_1)
        TestHelper.create_remote_file(sshcfg, cls.FILE_2_SUBPATH, cls.FILE_2_CONTENT)

    @logger_tm
    def test(self):
        '''Directories and files'''
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        path, dirs, files = os.walk(mountpoint).next()

        cls = TestDirectoriesAndFiles

        self.assertEqual(1, len(dirs))
        self.assertEqual(cls.SUBDIR_1, dirs[0])

        self.assertEqual(1, len(files))
        self.assertEqual(cls.FILE_1, files[0])

        file1_path = os.sep.join([mountpoint, files[0]])
        self.assertEqual(cls.FILE_1_CONTENT, open(file1_path).read())

        dir_path = os.sep.join([mountpoint, dirs[0]])

        def check_file():
            path, dirs, files = os.walk(dir_path).next()
            self.assertEqual(1, len(files))
            self.assertEqual(cls.FILE_2, files[0])
            file2_path = os.sep.join([mountpoint, cls.SUBDIR_1, cls.FILE_2])
            os.path.islink(file2_path)
            self.assertEqual(cls.FILE_2_CONTENT, open(file2_path).read())

        check_file()
        TestHelper.remove_remote_file(self.cfg.ssh, cls.FILE_2_SUBPATH)
        check_file() # after removing file remote it shall remain in cache
                     # contextual way of checking if cache is really working

class RelativePaths(SshCacheFsModuleTest):

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
        sshcfg = self.cfg.ssh
        cls = RelativePaths
        TestHelper.create_remote_dir(sshcfg, cls.SUBDIR)
        TestHelper.create_remote_file(sshcfg, cls.FILE, cls.FILE_CONTENT)

        TestHelper.create_remote_dir(sshcfg, cls.SUBDIR_2)
        TestHelper.create_remote_file(sshcfg, cls.FILE_2, cls.FILE_CONTENT_2)

        TestHelper.create_remote_dir(sshcfg, cls.SUBDIR_3)
        TestHelper.create_remote_file(sshcfg, cls.FILE_3, cls.FILE_CONTENT_3)

    def test(self):
        '''Relative paths'''

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

class SymbolicLinks(SshCacheFsModuleTest):

    def precondition(self):
        TestHelper.execute_remote(self.cfg.ssh, '''
            mkdir -p a/b/c

            mkdir -p e/f/g
            touch e/f/g/1.txt

            mkdir -p i/f/g
            touch i/f/g/2.txt

            ln -s ../../../i/f/g e/f/g/j''')

    def test(self):
        '''Symbolic links'''
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
        self.assertTrue(os.path.islink(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j/2.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))
        self.assertTrue(os.path.islink(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j/1.txt'])
        self.assertFalse(os.path.exists(full_path))


class CacheManagerModuleTest(ModuleTestCase):

    def setUpImpl(self):
        self.sshfs_manager = sshcachefs.SshfsManager(TestHelper.get_cfg_for_test().ssh)
        self.sut = sshcachefs.CacheManager(TestHelper.get_cfg_for_test().cache_manager,
                                           sshcachefs.SshCacheFs.SshfsAccess(self.sshfs_manager))
        TestHelper.create_remote_dir(self.sshfs_manager.cfg)
        self.sshfs_manager.run()
        self.sut.run()

    def tearDownImpl(self):
        self.sut.stop()
        self.sshfs_manager.stop()
        TestHelper.remove_remote_dir(self.sshfs_manager.cfg)
        shutil.rmtree(self.sut.cfg.cache_root_dir)


class CreateCacheDir(CacheManagerModuleTest):

    @logger_tm
    def test_create_cache_dir(self):
        self.assertTrue(os.path.exists(self.sut.cfg.cache_root_dir))

class DirInitStamp(CacheManagerModuleTest):

    @logger_tm
    def test_has_init_stamp(self):

        # UT
        self.assertFalse(self.sut._has_init_stamp('/'))
        self.sut.get_attributes('/')
        self.assertTrue(self.sut._has_init_stamp('/'))

class Exists(CacheManagerModuleTest):

    @logger_tm
    def test_exists(self):
        file_path = '/TestCacheManager.test_exists.txt'
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      '.' * 5)
        self.assertTrue(self.sut.exists(file_path))

class ExistsRoot(CacheManagerModuleTest):

    @logger_tm
    def test_exists_root(self):
        file_path = '/'
        self.assertTrue(self.sut.exists(file_path))

class IsFile(CacheManagerModuleTest):

    @logger_tm
    def test_is_file(self):
        file_path = '/TestCacheManager.test_is_file.txt'
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      ':' * 10)
        self.assertTrue(self.sut.exists(file_path))
        #self.assertTrue(self.sut.is_file(file_path))
        self.assertFalse(self.sut.is_dir(file_path))

class IsDir(CacheManagerModuleTest):

    @logger_tm
    def test_is_dir(self):
        dir_path = '/TestCacheManager.test_is_dir'
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)
        self.assertTrue(self.sut.exists(dir_path))
        self.assertTrue(self.sut.is_dir(dir_path))
        #self.assertFalse(self.sut.is_file(dir_path))

class GetPathToFile(CacheManagerModuleTest):

    @logger_tm
    def test_get_path_to_file(self):
        file_path = '/TestCacheManager.test_get_path_to_file.txt'
        file_content = '?' * 7
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      file_content)
        #cached_filepath = self.sut.get_path_to_file(file_path)
        # FIXME: maybe this test will be not needed
        #self.assertEqual(self.sut.cfg.cache_root_dir, os.path.dirname(cached_filepath))
        #self.assertTrue(os.path.exists(cached_filepath))
        #self.assertEqual(file_content, open(cached_filepath).read())

class GetPathToFileTwice(CacheManagerModuleTest):
    @logger_tm
    def test_get_path_to_file_twice_on_differrent_files(self):

        dir_path = '/TestCacheManager.test_get_path_to_file_twice_on_differrent_files'
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)
        dir_path = os.sep.join([dir_path, 'subdir'])
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)

        file_path = os.sep.join([dir_path, '1.txt'])
        file_content = '#' * 8
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      file_content)

        file_path2 = os.sep.join([dir_path, '2.txt'])
        file_content2 = '/' * 8
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path2,
                                      file_content2)

        #cached_filepath = self.sut.get_path_to_file(file_path)
        # FIXME: maybe remove (as above)
        #self.assertTrue(os.path.exists(cached_filepath))
        #self.assertEqual(file_content, open(cached_filepath).read())

       #cached_filepath2 = self.sut.get_path_to_file(file_path2)
        #self.assertTrue(os.path.exists(cached_filepath2))
        #self.assertEqual(file_content2, open(cached_filepath2).read())

class ListDir(CacheManagerModuleTest):
    @logger_tm
    def test_list_dir(self):
        dir_path = "/TestCacheManager.test_list_dir"
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)

        subdir_name = 'subdir'
        dir_path2 = os.sep.join([dir_path, subdir_name])
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path2)

        file_name = '1.txt'
        file_path = os.sep.join([dir_path, file_name])
        TestHelper.create_remote_file(self.sshfs_manager.cfg, file_path, 'file_content ... ')

        self.assertTrue(self.sut.exists(dir_path))
        #precond: 
        self.sut.get_attributes(dir_path)

        list_dir_out = self.sut.list_dir(dir_path)
        self.assertTrue(self.sut._has_init_stamp(dir_path))

        input = [file_name, subdir_name]
        self.assertEqual(sorted(input), sorted(list_dir_out))

        cache_root_path = self.sut.cfg.cache_root_dir 
        cache_dir_walker = sshcachefs.CacheManager.CachedDirWalker(cache_root_path)
        path_transformer = sshcachefs.CacheManager.PathTransformer()

        cached_subdir_path = os.sep.join(
            [cache_root_path, dir_path, path_transformer.transform_dirpath(subdir_name)])

        self.assertTrue(os.path.exists(cached_subdir_path))

        cached_file_path = os.sep.join(
            [cache_root_path, path_transformer.transform_filepath(file_name)])

        self.assertFalse(os.path.exists(cached_file_path))

class Getattr(CacheManagerModuleTest):
    @logger_tm
    def test(self):
        self.sut.get_attributes('.')

'''
class SshfsManagerModuleTest(ModuleTestCase):

    def setUpImpl(self):
        self.sut = sshcachefs.SshfsManager(TestHelper.get_cfg_for_test().ssh)
        self._umount_all()
        self._create_remote_dir()

    def tearDownImpl(self):
        self._remove_remote_dir()
        self._umount_all()
        #shutil.rmtree(TestHelper.get_cfg_for_test().ut_cleanup_dir)

    def _umount_all(self):
        self.sut.stop()

    def _create_remote_dir(self):
        TestHelper.create_remote_dir(self.sut.cfg)

    def _remove_remote_dir(self):
        pass

    def _local_path_of_file_in_sshfs(self, rel_filepath):
        return os.sep.join([self.sut.cfg.sshfs_mountpoint, rel_filepath])

    def _remove_remote_file(self, rel_filepath):
        self.assertTrue(os.path.ismount(self.sut.cfg.sshfs_mountpoint))
        os.remove(self._local_path_of_file_in_sshfs(rel_filepath))

    def _create_remote_file(self, rel_filepath, length):
        TestHelper.create_remote_file(self.sut.cfg, rel_filepath, '*' * length)

    def _read_remote_file(self, rel_filepath):
        self.assertTrue(os.path.ismount(self.sut.cfg.sshfs_mountpoint))
        f = open(self._local_path_of_file_in_sshfs(rel_filepath))
        buffer = f.read()
        f.close()
        return buffer


class RunStop(SshfsManagerModuleTest):

    def test_run_stop(self):
        self.sut.run()
        length = 1024;
        filename = 'test_run_stop___file'
        self._create_remote_file(filename, length)
        remote_file_content = self._read_remote_file(filename)

        self.assertEqual(length, len(remote_file_content))
        self._remove_remote_file(filename)

        # second attempt to remove the same file shall fail
        self.assertRaises(OSError, self._remove_remote_file, filename)
        self.assertRaises(IOError, self._read_remote_file, filename)

        self.sut.stop()

        self.assertFalse(os.path.ismount(self.sut.cfg.sshfs_mountpoint))

class StopWait2SecMountAfter1(SshfsManagerModuleTest):

    def test_stop_wait2sec_mountAfter1(self):
        self.sut.cfg.sshfs_bin = './bin_fakes/sshfs_fake.sh'
        self.sut.cfg.wait_for_mount = 2
        self.sut.cfg.sshfs_options.append('1') # interpreted by fake
        self.sut.run()

        length = 1024 * 200 # 200kb
        filename = 'test_run_stop___file'
        self._create_remote_file(filename, length)

        self.sut.stop()

        self.assertFalse(os.path.ismount(self.sut.cfg.sshfs_mountpoint))

class StopWait1SecMountAfter2(SshfsManagerModuleTest):

    def test_stop_wait1sec_mountAfter2(self):
        self.sut.cfg.sshfs_bin = './bin_fakes/sshfs_fake.sh'
        self.sut.cfg.wait_for_mount = 1
        self.sut.cfg.sshfs_options.append('2') # interpreted by fake

        self.assertRaises(sshcachefs.CriticalError, self.sut.run)
        self.sut.stop()

        self.assertFalse(os.path.ismount(self.sut.cfg.sshfs_mountpoint))

class MountpointDir(SshfsManagerModuleTest):

    def test_mountpoint_dir(self):
        mountpoint = self.sut.cfg.sshfs_mountpoint
        if os.path.exists(mountpoint):
            if os.path.isdir(mountpoint):
                shutil.rmtree(mountpoint, True)

        self.sut._create_dirs()

        self.assertTrue(os.path.exists(mountpoint))
        self.assertTrue(os.path.isdir(mountpoint))

class IsServing(SshfsManagerModuleTest):
    def test_is_serving(self):
        self.sut.run()
        self.assertTrue(self.sut.is_serving())
        self.sut.stop()
        self.assertFalse(self.sut.is_serving())

class IsServingMountAfter1Sec(SshfsManagerModuleTest):

    def test_is_serving_mountAfter1sec(self):
        self.sut.cfg.sshfs_bin = './bin_fakes/sshfs_fake.sh'
        self.sut.cfg.wait_for_mount = 5
        self.sut.cfg.sshfs_options.append('1')

        self.sut.run()
        self.assertTrue(self.sut.is_serving())
        self.sut.stop()
        self.assertFalse(self.sut.is_serving())

'''
