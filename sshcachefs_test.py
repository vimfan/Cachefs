import unittest
import shutil
import os
import subprocess
import time

import sshcachefs

class UtHelper:

    @staticmethod
    def getConfigForTest():
        config = sshcachefs.Config()

        config.server           = 'localhost'
        config.user             = 'seba'

        config.remote_dir       = '/home/seba/job/nsn/ssh_cache_fs/remote_dir'

        local_prefix            = '/home/seba/job/nsn/ssh_cache_fs/test'
        config.cache_root_dir   = local_prefix + 'cache'
        config.sshfs_mountpoint = local_prefix + 'sshfs_mountpoint'
        config.mountpoint       = local_prefix + 'mountpoint'
        
        config.ssh_bin          = '/usr/bin/ssh'
        config.fusermount_bin   = '/usr/bin/fusermount'

        return config


class TestSshCacheFs(unittest.TestCase):

    def setUp(self):
        self.config = UtHelper.getConfigForTest()
        self.sut = sshcachefs.SshCacheFs(self.config)

    def tearDown(self):
        pass

    def test_start(self):
        pass

class TestSshfsManager(unittest.TestCase):

    def setUp(self):
        self.config = UtHelper.getConfigForTest()
        self.sut = sshcachefs.SshFsManager(self.config.user,
                                           self.config.server,
                                           self.config.remote_dir,
                                           self.config.sshfs_mountpoint,
                                           self.config.sshfs_bin,
                                           self.config.fusermount_bin)
        self._umount_all()
        self._create_remote_dir()

    def tearDown(self):
        self._remove_remote_dir()
        self._umount_all()

    def test_mountpoint_dir(self):
        if os.path.exists(self.sut.mountpoint):
            if os.path.isdir(self.sut.mountpoint):
                try:
                    shutil.rmtree(self.sut.mountpoint, True)
                except:
                    print('cannot remove dirtree %s' % self.sut.mountpoint)
                    raise

        self.sut._create_dirs()

        self.assertTrue(os.path.exists(self.sut.mountpoint))
        self.assertTrue(os.path.isdir(self.sut.mountpoint))

    def _umount_all(self):
        self.sut.stop()

    def _create_remote_dir(self):
        # we're using localhost
        standalone_cmd = " ".join(['mkdir', '-p', self.config.remote_dir])
        user_host = "@".join([self.config.user, self.config.server])
        call_args = [self.config.ssh_bin, user_host, standalone_cmd]
        subprocess.call(call_args)

    def _remove_remote_dir(self):
        pass

    def _local_path_of_file_in_sshfs(self, rel_filepath):
        return os.path.sep.join([self.sut.mountpoint, rel_filepath])

    def _remove_remote_file(self, rel_filepath):
        self.assertTrue(os.path.ismount(self.sut.mountpoint))
        os.remove(self._local_path_of_file_in_sshfs(rel_filepath))

    def _create_remote_file(self, rel_filepath, length):
        self.assertTrue(os.path.ismount(self.sut.mountpoint))
        f = open(self._local_path_of_file_in_sshfs(rel_filepath), 'w')
        f.write('.' * length)
        f.close()

    def _read_remote_file(self, rel_filepath):
        self.assertTrue(os.path.ismount(self.sut.mountpoint))
        f = open(self._local_path_of_file_in_sshfs(rel_filepath))
        buffer = f.read()
        f.close()
        return buffer

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

        self.assertFalse(os.path.ismount(self.sut.mountpoint))

