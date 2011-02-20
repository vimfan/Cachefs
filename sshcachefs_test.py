import unittest
import shutil
import os
import subprocess
import time

import sshcachefs

class UtHelper:

    @staticmethod
    def getConfigForTest():

        config                      = sshcachefs.Config()

        common_prefix               = '/home/seba/job/nsn/ssh_cache_fs/test'

        # sshfs specific configuration options
        sshfs_prefix                = os.path.sep.join([common_prefix, 'sshfs'])
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


class TestSshCacheFs(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshCacheFs(UtHelper.getConfigForTest())

    def tearDown(self):
        pass

    def test_start(self):
        pass

    def test_stop(self):
        pass

class TestSshfsManager(unittest.TestCase):

    def setUp(self):
        self.sut = sshcachefs.SshfsManager(UtHelper.getConfigForTest().ssh)
        self._umount_all()
        self._create_remote_dir()

    def tearDown(self):
        self._remove_remote_dir()
        self._umount_all()

    def test_run(self):
        pass

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

    def test_stop_wait2sec_connectAfter1(self):
        self.sut.cfg.sshfs_bin = './bin_fakes/sshfs_fake.sh'
        self.sut.cfg.wait_for_mount = 2
        self.sut.cfg.sshfs_options.append('1') # interpreted by fake
        self.sut.run()

        length = 1024 * 200 # 200kb
        filename = 'test_run_stop___file'
        self._create_remote_file(filename, length)

        self.sut.stop()

        self.assertFalse(os.path.ismount(self.sut.cfg.sshfs_mountpoint))

    def test_stop_wait1sec_connectAfter2(self):
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

    def _umount_all(self):
        self.sut.stop()
        pass

    def _create_remote_dir(self):
        # we're using localhost
        standalone_cmd = " ".join(['mkdir', '-p', self.sut.cfg.remote_dir])
        user_host = "@".join([self.sut.cfg.user, self.sut.cfg.server])
        call_args = [self.sut.cfg.bin, user_host, standalone_cmd]
        subprocess.call(call_args)

    def _remove_remote_dir(self):
        pass

    def _local_path_of_file_in_sshfs(self, rel_filepath):
        return os.path.sep.join([self.sut.cfg.sshfs_mountpoint, rel_filepath])

    def _remove_remote_file(self, rel_filepath):
        self.assertTrue(os.path.ismount(self.sut.cfg.sshfs_mountpoint))
        os.remove(self._local_path_of_file_in_sshfs(rel_filepath))

    def _create_remote_file(self, rel_filepath, length):
        self.assertTrue(os.path.ismount(self.sut.cfg.sshfs_mountpoint))
        f = open(self._local_path_of_file_in_sshfs(rel_filepath), 'w')
        f.write('.' * length)
        f.close()

    def _read_remote_file(self, rel_filepath):
        self.assertTrue(os.path.ismount(self.sut.cfg.sshfs_mountpoint))
        f = open(self._local_path_of_file_in_sshfs(rel_filepath))
        buffer = f.read()
        f.close()
        return buffer

