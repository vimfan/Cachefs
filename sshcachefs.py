import sys
import os
import subprocess

class CriticalError(Exception):
    pass

class Config(object):

    def __init__(self):
        self.server = 'localhost'
        self.user = 'seba'

        self.remote_dir = '/studinfo/sebam'
        self.cache_root_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'

        self.sshfs_bin = '/usr/bin/sshfs'
        self.fusermount_bin = '/usr/bin/fusermount'
        self.sshfs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/.sshfs_mount'

        self.mountpoint = ' /home/seba/job/nsn/ssh_cache_fs/mountpoint'
        self.wait_for_mount = 30

class SshFsManager(object):

    def __init__(self, user, server, remote_dir, mountpoint, sshfs_bin, fusermount_bin):

        self.server = server
        self.user = user
        self.remote_dir = remote_dir
        self.mountpoint = mountpoint

        self.sshfs_bin = sshfs_bin
        self.fusermount_bin = fusermount_bin

    def run(self):
        user_host = "@".join([self.user, self.server])
        user_host_dir = ":".join([user_host, self.remote_dir])
        assert(0 == subprocess.call([self.sshfs_bin, user_host_dir, self.mountpoint]))
        self._wait_for_mount()

    def stop(self):
        if (os.path.ismount(self.mountpoint)):
            return subprocess.call([self.fusermount_bin, '-u', self.mountpoint])
        return 0

    def _wait_for_mount(self):

        def is_mount(obj):
            return os.path.ismount(obj.mountpoint)

        interval = 0.2
        time_elapsed = 0.0
        wait_for_mount = 30
        mounted = is_mount(self)
        while (not mounted and time_elapsed < wait_for_mount):
            time_elapsed += interval
            time.wait(interval)
            print time_elapsed
            mounted = is_mount(self)

    def _create_dirs(self):
        self._prepare_mountpoint_dir()

    def _prepare_mountpoint_dir(self):
        mountpoint = self.mountpoint

        if os.path.ismount(mountpoint):
            raise CriticalError("Cannot unmount filesystem: %s" 
                                % mountpoint)

        if os.path.isdir(mountpoint) and os.path.listdir(mountpoint):
            raise CriticalError(
                "Cannot mount Sshfs in %s, because directory is not empty" 
                % mountpoint)
        else:
            try:
                os.makedirs(mountpoint, 0700)
                return
            except:
                raise CriticalError("Cannot create directory %s" % mountpoint)

        # else directory is already created and most likely ready to mounting

class CacheManager(object):

    def __init__(self, cache_dir, remote_dir, sshfs_mountpoint):
        self.cache_dir = cache_dir
        self.remote_dir = remote_dir

    def run(self):
        pass

    def stop(self):
        pass

    def is_dir(self, path):
        pass

    def exists(self, path):
        # os.path.ismount()
        pass

    def _prepare_cache_root_dir(self):
        pass

    def _cache_root_dir(self):
        #nowstr = str(datetime.datetime.now()).replace(' ', '_')
        #pidstr = str(os.getpid())
        #cache_root = [self._config.cache_dir, pidstr, nowstr, self._config.remote_dir]
        #return "".join(cache_root)
        return self.cache_dir

class SshCacheFs(object):

    def __init__(self, config):
        self._config = config
        self._sshfs_manager = SshFsManager(self._config.user,
                                           self._config.server,
                                           self._config.remote_dir,
                                           self._config.mountpoint,
                                           self._config.sshfs_bin,
                                           self._config.fusermount_bin)

        self._cache_manager = CacheManager(self._config.cache_root_dir,
                                           self._config.remote_dir,
                                           self._config.mountpoint)

    def run(self):
        self._sshfs_manager.run()
        self._cache_manager.run()

    def stop(self):
        pass

    def readdir(self, path):
        pass

    def opendir(self, path):
        pass

    def releasedir(self, path):
        pass

    def access(self, path):
        pass

    def getattr(self, path):
        pass

    def fgetattr(self, path):
        pass

    def readlink(self, path):
        pass

    # file: open, read, flush, release
    # won't be implemented, becuase only symlinks
    # will be supported

    #def readdir(self, path):
        #self.readdir(path);

    #def readlink(self, path):
        #pass

