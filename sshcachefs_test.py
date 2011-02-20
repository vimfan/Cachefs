import unittest
import shutil
import os
import subprocess
import time
import tempfile

import sshcachefs

class TestHelper:

    @staticmethod
    def getConfigForTest():

        config                      = sshcachefs.Config()

        common_prefix               = '/home/seba/job/nsn/ssh_cache_fs/test'

        # sshfs specific configuration options
        sshfs_prefix                = os.path.sep.join([common_prefix, 'sshfs'])
        config.ut_cleanup_dir       = sshfs_prefix
        config.ssh.ut_ssh_bin       = '/usr/bin/ssh'
        config.ssh.ut_scp_bin       = '/usr/bin/scp'
        config.ssh.server           = 'localhost'
        config.ssh.user             = 'seba'
        config.ssh.remote_dir       = os.path.sep.join([sshfs_prefix, 'remote_dir'])
        config.ssh.sshfs_mountpoint = os.path.sep.join([sshfs_prefix, 'sshfs_mountpoint'])
        config.ssh.wait_for_mount   = 3.0
        config.ssh.sshfs_options    = ['-f']

        # cache manager specific config options
        cache_prefix                = common_prefix
        config.cache.cache_root_dir = os.path.sep.join([cache_prefix, 'cache'])

        # cache filesystem options
        config.mountpoint           = os.path.sep.join([common_prefix, 'mountpoint'])

        return config

    @staticmethod
    def create_remote_dir(cfg, path = ''):
        assert(isinstance(cfg, sshcachefs.Config.SshfsManagerConfig))
        if path:
            remote_dir = os.path.sep.join(cfg.remote_dir, path)
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


class TestSshCacheFs(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshCacheFs(TestHelper.getConfigForTest())

    def tearDown(self):
        pass

    def test_run(self):
        pass

    def test_stop(self):
        pass

class TestCacheManager(unittest.TestCase):

    def setUp(self):
        self.sshfs_manager = sshcachefs.SshfsManager(TestHelper.getConfigForTest().ssh)
        self.sut = sshcachefs.CacheManager(TestHelper.getConfigForTest().cache,
                                           sshcachefs.SshCacheFs.SshfsAccess(self.sshfs_manager))
        TestHelper.create_remote_dir(self.sshfs_manager.cfg)
        self.sshfs_manager.run()

    def tearDown(self):
        self.sshfs_manager.stop()

    def test_exists(self):

        file_path = 'TestCacheManager.test_exists.txt'

        TestHelper.create_remote_file(self.sshfs_manager.cfg, 
                                      file_path,
                                      'test_exists' * 5)

        self.assertTrue(self.sut.exists(file_path))

    def test_is_file(self):
        file_path = 'TestCacheManager.test_is_file.txt'

        TestHelper.create_remote_file(self.sshfs_manager.cfg,
                                      file_path,
                                      'test_is_file' * 10)

        self.assertTrue(self.sut.exists(file_path))
        self.assertTrue(self.sut.is_file(file_path))
        self.assertFalse(self.sut.is_dir(file_path))

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

