import sys

class Config(object):

    def __init__(self):
        self.sshfs_bin = '/usr/bin/sshfs'
        self.server = 'ultra60.mat.umk.pl'
        self.user = 'sebam'

        self.remote_path = '/studinfo/sebam'
        self.cache_dir = '/home/seba/job/nsn/env_proxy/.cache'

class SshFsManager(object):

    def __init__(self, user, server, remote_path, local_path):
        self.server = server
        self.user = user
        self.remote_path = remote_path
        self.local_path = local_path

    def run(self):
        pass

    def tearDown(self):
        pass

    def _mountpoint(self):
        return "".join([self._config.cache_dir, self._config.remote_path])


    def _create_dirs(self):
        self._create_mountpoint_dir()
        self._create_cache_dir()

    def _create_mountpoint_dir(self):
        import os
        mountpoint = self._mountpoint()
        if os.path.exists(mountpoint):
            if os.path.isdir(mountpoint)):
                try:
                    shutil.rmtree(mountpoint, True)
                except:
                    print('cannot remove dirtree %s' % mountpoint)

        try:
            os.mkdir(mountpoint, 0700)
        except:
            print('cannot create directory %s' % mountpoint)
            sys.exit(0);

    def _create_cache_dir():
        pass



class SshCacheFs(object):

    def __init__(self, config):
        self._config = config
        self._sshfs_manager = SshFsManager(self._config.user,
                                           self._config.server,
                                           self._config.remote_path,
                                           self._config.local_path)

    def run(self):
        self._sshfs_manager.run()

    def tearDown(self):
        pass

    #def readdir(self, path):
        #self.readdir(path);

    #def readlink(self, path):
        #pass

