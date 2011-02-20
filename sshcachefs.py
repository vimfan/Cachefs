import os
import shutil
import signal
import stat
import subprocess
import sys
import time

import fuse

class CriticalError(Exception):
    pass

class Config(object):

    class SshfsManagerConfig(object):
        def __init__(self):
            self.sshfs_bin        = '/usr/bin/sshfs'
            self.sshfs_options    = ['-f', '-o', 'follow_symlinks']
            self.fusermount_bin   = '/usr/bin/fusermount'
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
        self._is_serving = False

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
        self._is_serving = True

    def stop(self):
        if not self._ssh_process_handle:
            return
        mountpoint = self.cfg.sshfs_mountpoint
        if (os.path.ismount(mountpoint)):
            subprocess.call([self.cfg.fusermount_bin, '-u', mountpoint])
        else:
            pid = self._ssh_process_handle.pid
            os.kill(pid, signal.SIGINT)
        self._is_serving = False
        self._ssh_process_handle = None

    def is_serving(self):
        return self._is_serving

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
        # else directory is already created and seems to be ready to mounting

class CacheManager(object):

    def __init__(self, config, sshfs_access):
        assert(isinstance(config, Config.CacheManagerConfig))
        assert(isinstance(sshfs_access, SshCacheFs.SshfsAccess))
        self.cfg = config
        self.sshfs_access = sshfs_access

    def run(self):
        self._prepare_directories()

    def stop(self):
        pass

    def get_cached_file_path(self, origin_filepath):
        if not self._get_cache_path(origin_filepath):
            assert(self.sshfs_access.is_serving())
            self._create_local_copy(origin_filepath)
        return self._get_cache_path(origin_filepath)
        
    # getattr FS API equivalent
    def is_dir(self, path):
        st_mode = os.stat(self._absolute_remote_path(path)).st_mode
        #assert(not stat.S_ISLNK(st_mode))
        return stat.S_ISDIR(st_mode) 

    def is_file(self, path):
        st_mode = os.stat(self._absolute_remote_path(path)).st_mode
        # currently links are not supported, maybe support can be avoided by adding
        # option '-o follow-symbolic-links or similar' to sshfs
        #assert(not stat.S_ISLNK(st_mode)) 
        return stat.S_ISREG(st_mode) 

    # access FS API equivalent
    def exists(self, rel_path):
        if not self.sshfs_access.is_serving():
            return False
        path = os.path.sep.join([self.sshfs_access.mountpoint(), rel_path])
        return os.access(path, os.R_OK)

    def _create_local_copy(self, rel_filepath):
        src = os.path.sep.join([self.sshfs_access.mountpoint(), rel_filepath])
        dst = self._full_cache_path(rel_filepath)
        parent_dir = os.path.dirname(dst)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        shutil.copyfile(src, dst)

    def _get_cache_path(self, rel_filepath):
        full_path = self._full_cache_path(rel_filepath)
        if os.path.exists(full_path):
            return full_path
        return None

    def _full_cache_path(self, rel_filepath):
        root = self._cache_root_dir()
        return os.path.sep.join([root, rel_filepath])

    def _absolute_remote_path(self, rel_path):
        path = os.path.sep.join([self.sshfs_access.mountpoint(), rel_path])
        return path

    def _prepare_directories(self):
        dir = self._cache_root_dir()
        if not os.path.exists(dir):
            os.makedirs(dir)

    def _cache_root_dir(self):
        #nowstr = str(datetime.datetime.now()).replace(' ', '_')
        #pidstr = str(os.getpid())
        #cache_root = [self._config.cache_dir, pidstr, nowstr, self._config.remote_dir]
        #return "".join(cache_root)
        return self.cfg.cache_root_dir

class SshCacheFs(object):

    class SshfsAccess(object):
        def __init__(self, sshfs_manager):
            self._sshfs_mgr = sshfs_manager

        def mountpoint(self):
            return self._sshfs_mgr.cfg.sshfs_mountpoint

        def is_serving(self):
            return self._sshfs_mgr.is_serving()

    def __init__(self, config):
        self.cfg = config
        self._sshfs_manager = SshfsManager(self.cfg.ssh)
        self._cache_manager = CacheManager(self.cfg.cache, 
                                           SshCacheFs.SshfsAccess(self._sshfs_manager))

    def run(self):
        self._sshfs_manager.run()
        self._cache_manager.run()

    def stop(self):
        self._sshfs_manager.stop()

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

