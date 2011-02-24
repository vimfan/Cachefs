import unittest
import shutil
import os
import subprocess
import time
import tempfile
import config

import sshcachefs
import sshcachefs_runner

class TestHelper:

    @staticmethod
    def getConfigForTest():

        test_config                      = config.getConfig()
        common_prefix                    = '/home/seba/job/nsn/ssh_cache_fs/test'

        # sshfs specific configuration options
        sshfs_prefix                     = os.path.sep.join([common_prefix, 'sshfs'])
        test_config.ut_cleanup_dir       = sshfs_prefix
        test_config.ssh.ut_ssh_bin       = '/usr/bin/ssh'
        test_config.ssh.ut_scp_bin       = '/usr/bin/scp'
        test_config.ssh.server           = 'localhost'
        test_config.ssh.user             = 'seba'
        test_config.ssh.remote_dir       = os.path.sep.join([sshfs_prefix, 'remote_dir'])
        test_config.ssh.sshfs_mountpoint = os.path.sep.join([sshfs_prefix, 'sshfs_mountpoint'])
        test_config.ssh.wait_for_mount   = 3.0
        test_config.ssh.sshfs_options    = ['-f', '-o', 'follow_symlinks']

        # cache manager specific config options
        cache_prefix                            = common_prefix
        test_config.cacheManager.cache_root_dir = os.path.sep.join([cache_prefix, 'cache'])

        # cache filesystem options
        #test_config.mountpoint                  = os.path.sep.join([common_prefix, 'mountpoint'])

        test_config.cacheFs.cache_fs_mountpoint = os.path.sep.join([common_prefix, 'cache_fs_mountpoint'])

        return test_config

    @staticmethod
    def create_remote_dir(cfg, path = ''):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        if path:
            remote_dir = os.path.sep.join([cfg.remote_dir, path])
        else:
            remote_dir = cfg.remote_dir
        standalone_cmd = " ".join(['mkdir', '-p', remote_dir])
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
        path = os.path.sep.join([cfg.remote_dir, rel_path])
        user_host_path = ":".join([user_host, path])
        call_args = [cfg.ut_scp_bin, named_tmp_file.name, user_host_path]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))
        named_tmp_file.close() # automatically will be removed

def getConfig():
    return TestHelper.getConfigForTest()

class TestSshCacheFs(unittest.TestCase):

    def setUp(self):
        mountpoint = getConfig().cacheFs.cache_fs_mountpoint
        assert(not os.path.ismount(mountpoint))
        if not os.path.exists(mountpoint):
            os.makedirs(mountpoint)
        # by line below our getConfig() function will be used by
        # system under test
        self.runner = sshcachefs_runner.SshCacheFsRunner(__name__)
        self.runner.run()

    def tearDown(self):
        self.runner.stop()

    def test_copy(self):
        pass


class TestCacheManager(unittest.TestCase):

    def setUp(self):
        self.sshfs_manager = sshcachefs.SshfsManager(TestHelper.getConfigForTest().ssh)
        self.sut = sshcachefs.CacheManager(TestHelper.getConfigForTest().cacheManager,
                                           sshcachefs.SshCacheFs.SshfsAccess(self.sshfs_manager))
        TestHelper.create_remote_dir(self.sshfs_manager.cfg)
        self.sshfs_manager.run()
        self.sut.run()

    def tearDown(self):
        self.sut.stop()
        self.sshfs_manager.stop()
        shutil.rmtree(self.sut.cfg.cache_root_dir)

    def test_create_cache_dir(self):
        self.assertTrue(os.path.exists(self.sut.cfg.cache_root_dir))

    def test_exists(self):
        file_path = 'TestCacheManager.test_exists.txt'
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      '.' * 5)
        self.assertTrue(self.sut.exists(file_path))

    def test_is_file(self):
        file_path = 'TestCacheManager.test_is_file.txt'
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      ':' * 10)
        self.assertTrue(self.sut.exists(file_path))
        self.assertTrue(self.sut.is_file(file_path))
        self.assertFalse(self.sut.is_dir(file_path))

    def test_is_dir(self):
        dir_path = 'TestCacheManager.test_is_dir'
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)
        self.assertTrue(self.sut.exists(dir_path))
        self.assertTrue(self.sut.is_dir(dir_path))
        self.assertFalse(self.sut.is_file(dir_path))

    def test_get_cached_file_path(self):
        file_path = 'TestCacheManager.test_get_cached_file_path.txt'
        file_content = '?' * 7
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      file_content)
        cached_filepath = self.sut.get_cached_file_path(file_path)
        self.assertEqual(self.sut.cfg.cache_root_dir, os.path.dirname(cached_filepath))
        self.assertTrue(os.path.exists(cached_filepath))
        self.assertEqual(file_content, open(cached_filepath).read())

    def test_get_cached_file_path_twice_on_differrent_files(self):

        dir_path = 'TestCacheManager.test_get_cached_file_path_twice_on_differrent_files'
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)
        dir_path = os.path.sep.join([dir_path, 'subdir'])
        TestHelper.create_remote_dir(self.sshfs_manager.cfg, dir_path)

        file_path = os.path.sep.join([dir_path, '1.txt'])
        file_content = '#' * 8
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      file_content)

        file_path2 = os.path.sep.join([dir_path, '2.txt'])
        file_content2 = '/' * 8
        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path2,
                                      file_content2)

        cached_filepath = self.sut.get_cached_file_path(file_path)
        self.assertTrue(os.path.exists(cached_filepath))
        self.assertEqual(file_content, open(cached_filepath).read())

        cached_filepath2 = self.sut.get_cached_file_path(file_path2)
        self.assertTrue(os.path.exists(cached_filepath2))
        self.assertEqual(file_content2, open(cached_filepath2).read())

class TestSshfsManager(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshfsManager(TestHelper.getConfigForTest().ssh)
        self._umount_all()
        self._create_remote_dir()

    def tearDown(self):
        self._remove_remote_dir()
        self._umount_all()
        shutil.rmtree(TestHelper.getConfigForTest().ut_cleanup_dir)

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
        pass

    def _create_remote_dir(self):
        TestHelper.create_remote_dir(self.sut.cfg)

    def _remove_remote_dir(self):
        pass

    def _local_path_of_file_in_sshfs(self, rel_filepath):
        return os.path.sep.join([self.sut.cfg.sshfs_mountpoint, rel_filepath])

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

