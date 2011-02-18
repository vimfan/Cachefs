import sys
import os

class Config(object):

    def __init__(self):
        self.server = 'ultra60.mat.umk.pl'
        self.user = 'sebam'

        self.remote_dir = '/studinfo/sebam'
        self.cache_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'

        self.sshfs_bin = '/usr/bin/sshfs'
        self.sshfs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/.sshfs_mount'

        self.mountpoint = ' /home/seba/job/nsn/ssh_cache_fs/mountpoint'

class SshFsManager(object):

    def __init__(self, user, server, remote_dir, mountpoint):
        self.server = server
        self.user = user
        self.remote_dir = remote_dir
        self.mountpoint = mountpoint

    def run(self):
        pass

    def tearDown(self):
        pass

    def _mountpoint(self):
        return self.mountpoint

    def _cache_root_dir(self):
        nowstr = str(datetime.datetime.now()).replace(' ', '_')
        pidstr = str(os.getpid())
        return "".join([self._config.cache_dir, pidstr, nowstr, self._config.remote_dir])


    def _create_dirs(self):
        self._create_mountpoint_dir()
        self._create_cache_dir()

    def _create_mountpoint_dir(self):
        import os
        mountpoint = self._mountpoint()
        if os.path.exists(mountpoint):
            if os.path.isdir(mountpoint):
                try:
                    shutil.rmtree(mountpoint, True)
                except:
                    print('cannot remove dirtree %s' % mountpoint)

        try:
            os.mkdir(mountpoint, 0700)
        except:
            print('cannot create directory %s' % mountpoint)
            sys.exit(0);

    def _create_cache_dir(self):
        pass

class CacheManager(object):
    pass

class SshCacheFs(object):

    def __init__(self, config):
        self._config = config
        self._sshfs_manager = SshFsManager(self._config.user,
                                           self._config.server,
                                           self._config.remote_dir,
                                           self._config.mountpoint)

    def run(self):
        self._sshfs_manager.run()

    def tearDown(self):
        pass

    #def readdir(self, path):
        #self.readdir(path);

    #def readlink(self, path):
        #pass

