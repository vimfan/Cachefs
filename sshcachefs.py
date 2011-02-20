import sys
import os
import time
import subprocess
import signal

class CriticalError(Exception):
    pass

class Config(object):

    class SshfsManagerConfig(object):
        def __init__(self):
            self.sshfs_bin        = '/usr/bin/sshfs'
            self.sshfs_options    = ['-f']
            self.fusermount_bin   = '/usr/bin/fusermount'
            self.bin              = '/usr/bin/ssh'
            self.sshfs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/.sshfs_mount'
            self.server           = 'localhost'
            self.user             = 'seba'
            self.remote_dir       = '/studinfo/sebam'
            self.wait_for_mount   = 30

    class CacheManagerConfig(object):

        def __init__(self):
            self.cache_root_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'

    def __init__(self):
        self.ssh = Config.SshfsManagerConfig()
        self.cache = Config.CacheManagerConfig()

class SshfsManager(object):

    def __init__(self, config):
        assert(isinstance(config, Config.SshfsManagerConfig))
        self.cfg = config
        self._ssh_process_handle = None

    def run(self):
        self._create_dirs()
        cfg = self.cfg
        user_host = "@".join([cfg.user, cfg.server])
        user_host_dir = ":".join([user_host, cfg.remote_dir])
        args = [cfg.sshfs_bin, user_host_dir, cfg.sshfs_mountpoint]
        if cfg.sshfs_options:
            args.extend(cfg.sshfs_options) 
        self._ssh_process_handle = subprocess.Popen(args)
        self._wait_for_mount()

    def stop(self):
        if not self._ssh_process_handle:
            return

        mountpoint = self.cfg.sshfs_mountpoint
        if (os.path.ismount(mountpoint)):
            subprocess.call([self.cfg.fusermount_bin, '-u', mountpoint])
        else:
            pid = self._ssh_process_handle.pid
            os.kill(pid, signal.SIGINT)

        self._ssh_process_handle = None

    def _wait_for_mount(self):
        assert(self.cfg)
        assert(self.cfg.sshfs_mountpoint)
        assert(self.cfg.wait_for_mount)
        assert(self._ssh_process_handle)

        mountpoint = self.cfg.sshfs_mountpoint

        def is_mount():
            return os.path.ismount(mountpoint)

        interval = 0.2
        wait_for_mount = self.cfg.wait_for_mount
        time_start = time.time()
        time_elapsed = 0
        mounted = is_mount()
        while ((not mounted) and time_elapsed < wait_for_mount):
            time.sleep(interval)
            mounted = is_mount()
            time_elapsed = time.time() - time_start
        if not mounted:
            raise CriticalError("Filesystem not mounted after %d secs" % wait_for_mount)

    def _create_dirs(self):
        self._prepare_mountpoint_dir()

    def _prepare_mountpoint_dir(self):
        mountpoint = self.cfg.sshfs_mountpoint
        assert(mountpoint and isinstance(mountpoint, str))

        if os.path.ismount(mountpoint):
            raise CriticalError("Cannot unmount filesystem: %s" 
                                % mountpoint)

        if os.path.isdir(mountpoint) and os.listdir(mountpoint):
            raise CriticalError(
                "Cannot mount Sshfs in %s, because directory is not empty" 
                % mountpoint)

        if not os.path.isdir(mountpoint):
            try:
                os.makedirs(mountpoint, 0700)
                return
            except:
                raise CriticalError("Cannot create directory %s" % mountpoint)

        # else directory is already created and most likely ready to mounting

class CacheManager(object):

    def __init__(self, config):
        assert(isinstance(config, Config.CacheManagerConfig))
        self.cfg = config

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
        return self.cfg.cache_dir

class SshCacheFs(object):

    def __init__(self, config):
        self.cfg = config
        self._sshfs_manager = SshfsManager(self.cfg.ssh)
        self._cache_manager = CacheManager(self.cfg.cache)

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

