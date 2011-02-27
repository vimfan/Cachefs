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

def logger_ut(f):
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

class SshCacheFsUnitTest(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshCacheFs(TestHelper.get_cfg_for_test())

    def tearDown(self):
        pass

    @logger_ut
    def test_getattr(self):
        # inject mock
        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)

        def configure_cache_mgr(path, exists = True, is_dir = False, is_file = False):
            cache_mgr_mock.exists(path).AndReturn(exists)
            if exists:
                cache_mgr_mock.is_dir(path).AndReturn(is_dir)
            if exists and not is_dir: # is file
                cache_mgr_mock.is_file(path).AndReturn(is_file)

        # configure mock
        configure_cache_mgr('.', is_dir=True)
        configure_cache_mgr('file.txt', is_file=True) 
        configure_cache_mgr('directory', is_dir=True)
        configure_cache_mgr('link', is_dir=False, is_file=False)

        mox.Replay(cache_mgr_mock)

        # check output
        self.assertTrue(stat.S_ISDIR(self.sut.getattr('.').st_mode))
        self.assertTrue(stat.S_ISLNK(self.sut.getattr('file.txt').st_mode))
        self.assertTrue(stat.S_ISDIR(self.sut.getattr('directory').st_mode))
        self.assertEqual(-errno.ENOENT, self.sut.getattr('link'))

    @logger_ut
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

    @logger_ut
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

    @logger_ut
    def test_readdir_dir_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    @logger_ut
    def test_readdir_on_file(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    @logger_ut
    def test_opendir_success(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(True)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.opendir(DIRPATH))

    @logger_ut
    def test_opendir_not_dir(self):
        FILEPATH = '/FILE'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(FILEPATH).AndReturn(True)
        cache_mgr_mock.is_dir(FILEPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(FILEPATH))

    @logger_ut
    def test_opendir_path_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(DIRPATH))

    @logger_ut
    def test_readlink_success(self):
        FILEPATH = '/File'
        CACHED_FILE_PATH = "/ABSOLUTE/PATH/TO/CACHED/FILE"

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.get_path_to_file(FILEPATH).AndReturn(CACHED_FILE_PATH)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(CACHED_FILE_PATH, self.sut.readlink(FILEPATH))

    @logger_ut
    def test_readlink_not_found(self):
        FILEPATH = '/File'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(sshcachefs.CacheManager)
        cache_mgr_mock.get_path_to_file(FILEPATH).AndReturn(None)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.readlink(FILEPATH))

class SshCacheFsModuleTest(unittest.TestCase):

    def setUp(self):
        cfg = self.cfg = TestHelper.get_cfg_for_test()
        mountpoint = cfg.cache_fs.cache_fs_mountpoint
        self.assertTrue(not os.path.ismount(mountpoint), msg=mountpoint)
        if not os.path.exists(mountpoint):
            os.makedirs(mountpoint)
        TestHelper.create_remote_dir(cfg.ssh)
        self.runner = runner.SshCacheFsRunner(test_config)
        self.runner.run()

    def tearDown(self):
        self.runner.stop()
        TestHelper.remove_remote_dir(self.cfg.ssh)
        # add some safety checks
        assert(self.cfg.cache_manager.cache_root_dir)
        shutil.rmtree(self.cfg.cache_manager.cache_root_dir)

    @logger_ut
    def test_directories_only(self):
        SUBDIR_1 = 'subdir1'
        SUBDIR_2 = 'subdir2'
        SUB_SUBDIR_2 = 'subdir2.1'

        sshcfg = self.cfg.ssh
        TestHelper.create_remote_dir(sshcfg, SUBDIR_1)
        TestHelper.create_remote_dir(sshcfg, SUBDIR_2)
        TestHelper.create_remote_dir(sshcfg, os.sep.join([SUBDIR_2, SUB_SUBDIR_2]))

        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        entries = os.listdir(mountpoint)
        self.assertTrue(SUBDIR_1 in entries)
        self.assertTrue(SUBDIR_2 in entries)

        cache_root = self.cfg.cache_manager.cache_root_dir

        cache_entries = os.listdir(mountpoint)
        self.assertEqual(sorted([SUBDIR_1, SUBDIR_2]), sorted(cache_entries))

        entries_subdir2 = os.listdir(os.sep.join([mountpoint, SUBDIR_2]))
        self.assertEqual([SUB_SUBDIR_2], entries_subdir2)


class CacheManagerModuleTest(unittest.TestCase):

    def setUp(self):
        self.sshfs_manager = sshcachefs.SshfsManager(TestHelper.get_cfg_for_test().ssh)
        self.sut = sshcachefs.CacheManager(TestHelper.get_cfg_for_test().cache_manager,
                                           sshcachefs.SshCacheFs.SshfsAccess(self.sshfs_manager))
        TestHelper.create_remote_dir(self.sshfs_manager.cfg)
        self.sshfs_manager.run()
        self.sut.run()

    def tearDown(self):
        self.sut.stop()
        self.sshfs_manager.stop()
        TestHelper.remove_remote_dir(self.sshfs_manager.cfg)
        shutil.rmtree(self.sut.cfg.cache_root_dir)

    @logger_ut
    def test_create_cache_dir(self):
        self.assertTrue(os.path.exists(self.sut.cfg.cache_root_dir))

    @logger_ut
    def test_exists(self):
        file_path = '/TestCacheManager.test_exists.txt'
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      '.' * 5)
        self.assertTrue(self.sut.exists(file_path))

    @logger_ut
    def test_exists_root(self):
        file_path = '/'
        self.assertTrue(self.sut.exists(file_path))

    @logger_ut
    def test_is_file(self):
        file_path = '/TestCacheManager.test_is_file.txt'
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      ':' * 10)
        self.assertTrue(self.sut.exists(file_path))
        self.assertTrue(self.sut.is_file(file_path))
        self.assertFalse(self.sut.is_dir(file_path))

    @logger_ut
    def test_is_dir(self):
        dir_path = '/TestCacheManager.test_is_dir'
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)
        self.assertTrue(self.sut.exists(dir_path))
        self.assertTrue(self.sut.is_dir(dir_path))
        self.assertFalse(self.sut.is_file(dir_path))

    @logger_ut
    def test_get_path_to_file(self):
        file_path = '/TestCacheManager.test_get_path_to_file.txt'
        file_content = '?' * 7
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      file_content)
        cached_filepath = self.sut.get_path_to_file(file_path)
        # FIXME: maybe this test will be not needed
        #self.assertEqual(self.sut.cfg.cache_root_dir, os.path.dirname(cached_filepath))
        #self.assertTrue(os.path.exists(cached_filepath))
        #self.assertEqual(file_content, open(cached_filepath).read())

    @logger_ut
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

        cached_filepath = self.sut.get_path_to_file(file_path)
        # FIXME: maybe remove (as above)
        #self.assertTrue(os.path.exists(cached_filepath))
        #self.assertEqual(file_content, open(cached_filepath).read())

       #cached_filepath2 = self.sut.get_path_to_file(file_path2)
        #self.assertTrue(os.path.exists(cached_filepath2))
        #self.assertEqual(file_content2, open(cached_filepath2).read())

    @logger_ut
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
        list_dir_out = self.sut.list_dir(dir_path)
        input = [file_name, subdir_name]
        self.assertEqual(sorted(input), sorted(list_dir_out))

        cache_root_path = self.sut.cfg.cache_root_dir 
        cache_dir_walker = sshcachefs.CacheManager.CachedDirWalker(cache_root_path)

        self.assertTrue(self.sut._has_initialization_stamp(dir_path))

        cached_subdir_path = os.sep.join(
            [cache_root_path, dir_path, cache_dir_walker.transform_dirname(subdir_name)])

        self.assertTrue(os.path.exists(cached_subdir_path))

        cached_file_path = os.sep.join(
            [cache_root_path, cache_dir_walker.transform_filename(file_name)])

        self.assertFalse(os.path.exists(cached_file_path))

class SshfsManagerModuleTest(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshfsManager(TestHelper.get_cfg_for_test().ssh)
        self._umount_all()
        self._create_remote_dir()

    def tearDown(self):
        self._remove_remote_dir()
        self._umount_all()
        shutil.rmtree(TestHelper.get_cfg_for_test().ut_cleanup_dir)

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

    def test_stop_wait1sec_mountAfter2(self):
        self.sut.cfg.sshfs_bin = './bin_fakes/sshfs_fake.sh'
        self.sut.cfg.wait_for_mount = 1
        self.sut.cfg.sshfs_options.append('2') # interpreted by fake

        self.assertRaises(sshcachefs.CriticalError, self.sut.run)
        self.sut.stop()

        self.assertFalse(os.path.ismount(self.sut.cfg.sshfs_mountpoint))


    def test_mountpoint_dir(self):
        mountpoint = self.sut.cfg.sshfs_mountpoint
        if os.path.exists(mountpoint):
            if os.path.isdir(mountpoint):
                shutil.rmtree(mountpoint, True)

        self.sut._create_dirs()

        self.assertTrue(os.path.exists(mountpoint))
        self.assertTrue(os.path.isdir(mountpoint))

    def test_is_serving(self):
        self.sut.run()
        self.assertTrue(self.sut.is_serving())
        self.sut.stop()
        self.assertFalse(self.sut.is_serving())

    def test_is_serving_mountAfter1sec(self):
        self.sut.cfg.sshfs_bin = './bin_fakes/sshfs_fake.sh'
        self.sut.cfg.wait_for_mount = 5
        self.sut.cfg.sshfs_options.append('1')

        self.sut.run()
        self.assertTrue(self.sut.is_serving())
        self.sut.stop()
        self.assertFalse(self.sut.is_serving())

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

