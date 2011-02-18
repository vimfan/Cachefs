import unittest
import sshcachefs
import shutil

class UtHelper:

    @staticmethod
    def getDefaultConfig():
        return sshcachefs.Config()


class TestSshCacheFs(unittest.TestCase):

    def setUp(self):
        self.config = UtHelper.getDefaultConfig()
        self.sut = sshcachefs.SshCacheFs(self.config)

    def tearDown(self):
        pass

    def test_start(self):
        pass

class TestSshfsManager(unittest.TestCase):

    def setUp(self):
        self.config = UtHelper.getDefaultConfig()
        self.sut = SshFsManager(self._config.user,
                                self._config.server,
                                self._config.remote_path,
                                self._config.local_path)

    def tearDown(self):
        pass

    def test_create_cache_dir(self):
        import os
        if os.path.exists(self.sut._mountpoint()):
            if os.path.isdir(self.sut._mountpoint()):
                try:
                    shutil.rmtree(self.sut._mountpoint(), True)
                except:
                    print('cannot remove dirtree %s' % self.sut._mountpoint())

        self.sut._create_dirs()

        self.assertTrue(os.path.exists(self.sut._mountpoint()))
        self.assertTrue(os.path.isdir(self.sut._mountpoint()))


