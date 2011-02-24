
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
import logging
import datetime
import calendar

import errno
import stat    # for file properties
import os      # for filesystem modes (O_RDONLY, etc)

if __name__ == '__main__':
    # FIXME
    # now we invoke it in clumsy way
    # script.py mountpoint config_module
    assert(len(sys.argv) >= 3)
    import_config = sys.argv[2]
    del sys.argv[2]
    exec('import %s as config' % import_config)
else:
    import config

import fuse

# FUSE version at the time of writing. Be compatible with this version.
fuse.fuse_python_api = (0, 2)

LOG_FILENAME = "LOG"
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,)

class CriticalError(Exception):
    pass

class SshfsManager(object):

    def __init__(self, cfg):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        self.cfg = cfg
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

    def __init__(self, cfg, sshfs_access):
        assert(isinstance(cfg, config.Config.CacheManagerConfig))
        assert(isinstance(sshfs_access, SshCacheFs.SshfsAccess))
        self.cfg = cfg
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

class Stat(fuse.Stat):
    """
    A Stat object. Describes the attributes of a file or directory.
    Has all the st_* attributes, as well as dt_atime, dt_mtime and dt_ctime,
    which are datetime.datetime versions of st_*time. The st_*time versions
    are in epoch time.
    """
    # Filesize of directories, in bytes.
    DIRSIZE = 4096

    # We can define __init__ however we like, because it's only called by us.
    # But it has to have certain fields.
    def __init__(self, st_mode, st_size, st_nlink=1, st_uid=None, st_gid=None,
            dt_atime=None, dt_mtime=None, dt_ctime=None):
        """
        Creates a Stat object.
        st_mode: Required. Should be stat.S_IFREG or stat.S_IFDIR ORed with a
            regular Unix permission value like 0644.
        st_size: Required. Size of file in bytes. For a directory, should be
            Stat.DIRSIZE.
        st_nlink: Number of hard-links to the file. Regular files should
            usually be 1 (default). Directories should usually be 2 + number
            of immediate subdirs (one from the parent, one from self, one from
            each child).
        st_uid, st_gid: uid/gid of file owner. Defaults to the user who
            mounted the file system.
        st_atime, st_mtime, st_ctime: atime/mtime/ctime of file.
            (Access time, modification time, stat change time).
            These must be datetime.datetime objects, in UTC time.
            All three values default to the current time.
        """
        self.st_mode = st_mode
        self.st_ino = 2         # Ignored, but required
        self.st_dev = 1        # Ignored, but required
        # Note: Wiki says st_blksize is required (like st_dev, ignored but
        # required). However, this breaks things and another tutorial I found
        # did not have this field.
        self.st_nlink = st_nlink
        if st_uid is None:
            st_uid = os.getuid()
        self.st_uid = st_uid
        if st_gid is None:
            st_gid = os.getgid()
        self.st_gid = st_gid
        self.st_size = st_size
        now = datetime.datetime.utcnow()
        self.dt_atime = dt_atime or now
        self.dt_mtime = dt_mtime or now
        self.dt_ctime = dt_ctime or now

    def __repr__(self):
        return ("<Stat st_mode %s, st_nlink %s, st_uid %s, st_gid %s, "
            "st_size %s>" % (self.st_mode, self.st_nlink, self.st_uid,
            self.st_gid, self.st_size))

    def _get_dt_atime(self):
        return self.epoch_datetime(self.st_atime)
    def _set_dt_atime(self, value):
        self.st_atime = self.datetime_epoch(value)
    dt_atime = property(_get_dt_atime, _set_dt_atime)

    def _get_dt_mtime(self):
        return self.epoch_datetime(self.st_mtime)
    def _set_dt_mtime(self, value):
        self.st_mtime = self.datetime_epoch(value)
    dt_mtime = property(_get_dt_mtime, _set_dt_mtime)

    def _get_dt_ctime(self):
        return self.epoch_datetime(self.st_ctime)
    def _set_dt_ctime(self, value):
        self.st_ctime = self.datetime_epoch(value)
    dt_ctime = property(_get_dt_ctime, _set_dt_ctime)

    @staticmethod
    def datetime_epoch(dt):
        """
        Converts a datetime.datetime object which is in UTC time
        (as returned by datetime.datetime.utcnow()) into an int, which represents
        the number of seconds since the system epoch (also in UTC time).
        """
        # datetime.datetime.timetuple converts a datetime into a time.struct_time.
        # calendar.timegm converts a time.struct_time into epoch time, without
        # modifying for time zone (so UTC time stays in UTC time, unlike
        # time.mktime).
        return calendar.timegm(dt.timetuple())
    @staticmethod
    def epoch_datetime(seconds):
        """
        Converts an int, the number of seconds since the system epoch in UTC
        time, into a datetime.datetime object, also in UTC time.
        """
        return datetime.datetime.utcfromtimestamp(seconds)

    def set_times_to_now(self, atime=False, mtime=False, ctime=False):
        """
        Sets one or more of atime, mtime and ctime to the current time.
        atime, mtime, ctime: All booleans. If True, this value is updated.
        """
        now = datetime.datetime.utcnow()
        if atime:
            self.dt_atime = now
        if mtime:
            self.dt_mtime = now
        if ctime:
            self.dt_ctime = now

    def check_permission(self, uid, gid, flags):
        """
        Checks the permission of a uid:gid with given flags.
        Returns True for allowed, False for denied.
        flags: As described in man 2 access (Linux Programmer's Manual).
            Either os.F_OK (test for existence of file), or ORing of
            os.R_OK, os.W_OK, os.X_OK (test if file is readable, writable and
            executable, respectively. Must pass all tests).
        """
        if flags == os.F_OK:
            return True
        user = (self.st_mode & 0700) >> 6
        group = (self.st_mode & 070) >> 3
        other = self.st_mode & 07
        if uid == self.st_uid:
            # Use "user" permissions
            mode = user | group | other
        elif gid == self.st_gid:
            # Use "group" permissions
            # XXX This will only check the user's primary group. Don't we need
            # to check all the groups this user is in?
            mode = group | other
        else:
            # Use "other" permissions
            mode = other
        if flags & os.R_OK:
            if mode & os.R_OK == 0:
                return False
        if flags & os.W_OK:
            if mode & os.W_OK == 0:
                return False
        if flags & os.X_OK:
            if uid == 0:
                # Root has special privileges. May execute if anyone can.
                if mode & 0111 == 0:
                    return False
            else:
                if mode & os.X_OK == 0:
                    return False
        return True

class SshCacheFs(fuse.Fuse):

    class SshfsAccess(object):

        def __init__(self, sshfs_manager):
            self._sshfs_mgr = sshfs_manager

        def mountpoint(self):
            return self._sshfs_mgr.cfg.sshfs_mountpoint

        def is_serving(self):
            return self._sshfs_mgr.is_serving()

    def __init__(self, cfg, *args, **kw):
        #super(SshCacheFs, self).__init__(*args, **kwargs)
        fuse.Fuse.__init__(self, *args, **kw)
        self.__cfg = cfg
        #self._sshfs_manager = SshfsManager(self.cfg.ssh)
        #self._cache_manager = CacheManager(self.cfg.cache, 
        #                                   SshCacheFs.SshfsAccess(self._sshfs_manager))

    def run(self):
        #self._sshfs_manager.run()
        #self._cache_manager.run()
        self.main()

    def stop(self):
        #self._sshfs_manager.stop()
        pass

    def getattr(self, path):
        """
        - st_mode (protection bits)
        - st_ino (inode number)
        - st_dev (device)
        - st_nlink (number of hard links)
        - st_uid (user ID of owner)
        - st_gid (group ID of owner)
        - st_size (size of file, in bytes)
        - st_atime (time of most recent access)
        - st_mtime (time of most recent content modification)
        - st_ctime (platform dependent; time of most recent metadata change on Unix,
                    or the time of creation on Windows).
        """
        print '*** getattr', path
        if path == '/':
            return Stat(stat.S_IFREG | 644, 1);
        #depth = getDepth(path) # depth of path, zero-based from root
        #pathparts = getParts(path) # the actual parts of the path
        return -errno.ENOSYS


    def getdir(self, path):
        """
        return: [[('file1', 0), ('file2', 0), ... ]]
        """

        print '*** getdir', path
        return -errno.ENOSYS

    def mythread ( self ):
        print '*** mythread'
        return -errno.ENOSYS

    def chmod ( self, path, mode ):
        print '*** chmod', path, oct(mode)
        return -errno.ENOSYS

    def chown ( self, path, uid, gid ):
        print '*** chown', path, uid, gid
        return -errno.ENOSYS

    def fsync ( self, path, isFsyncFile ):
        print '*** fsync', path, isFsyncFile
        return -errno.ENOSYS

    def link ( self, targetPath, linkPath ):
        print '*** link', targetPath, linkPath
        return -errno.ENOSYS

    def mkdir ( self, path, mode ):
        print '*** mkdir', path, oct(mode)
        return -errno.ENOSYS

    def mknod ( self, path, mode, dev ):
        print '*** mknod', path, oct(mode), dev
        return -errno.ENOSYS

    def open ( self, path, flags ):
        print '*** open', path, flags
        return -errno.ENOSYS

    def read ( self, path, length, offset ):
        print '*** read', path, length, offset
        return -errno.ENOSYS

    def readlink ( self, path ):
        print '*** readlink', path
        return -errno.ENOSYS

    def release ( self, path, flags ):
        print '*** release', path, flags
        return -errno.ENOSYS

    def rename ( self, oldPath, newPath ):
        print '*** rename', oldPath, newPath
        return -errno.ENOSYS

    def rmdir ( self, path ):
        print '*** rmdir', path
        return -errno.ENOSYS

    def statfs ( self ):
        print '*** statfs'
        return -errno.ENOSYS

    def symlink ( self, targetPath, linkPath ):
        print '*** symlink', targetPath, linkPath
        return -errno.ENOSYS

    def truncate ( self, path, size ):
        print '*** truncate', path, size
        return -errno.ENOSYS

    def unlink ( self, path ):
        print '*** unlink', path
        return -errno.ENOSYS

    def utime ( self, path, times ):
        print '*** utime', path, times
        return -errno.ENOSYS

    def write ( self, path, buf, offset ):
        print '*** write', path, buf, offset
        return -errno.ENOSYS

    #def readlink(self, path):
        #return -errno.ENOSYS

    def readdir(self, path):
        yield fuse.Direntry(".")
        yield fuse.Direntry("..")

    #def opendir(self, path):
        #return -errno.ENOSYS

    #def releasedir(self, path):
        #return -errno.ENOSYS

    #def access(self, path):
        #return -errno.ENOSYS

    #def getattr(self, path):
        #return -errno.ENOSYS

    #def fgetattr(self, path):
        #return -errno.ENOSYS

    # file: open, read, flush, release
    # won't be implemented, becuase only symlinks
    # will be supported

    #def readdir(self, path):
        #self.readdir(path);

    #def readlink(self, path):
        #pass

def main():
    usage = """
    SshCacheFs: Sshfs read-only cache virtual filesystem.
    """ + fuse.Fuse.fusage
    server = SshCacheFs(config.getConfig(),
                        version="%prog " + fuse.__version__,
                        usage=usage,
                        dash_s_do='setsingle')

    server.flags = 0
    server.parse(errex=1)
    server.multithreaded = 0
    try:
        #server.run()
        server.main()
    except fuse.FuseError, e:
        print str(e)

if __name__ == '__main__':
    main()

logging.info("File system unmounted")
