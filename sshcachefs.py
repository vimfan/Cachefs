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

######################
# TODO: treat directories in special way: 
#       if creation time of directory is older than some configurable value (e.g. one hour)
#       than reread directory from source
#####################

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

import config as config_canonical

import fuse

# FUSE version at the time of writing. Be compatible with this version.
fuse.fuse_python_api = (0, 2)

LOG_FILENAME = "LOG"
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,)

class CriticalError(Exception):
    pass

class FsObject(object):

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.name)

class Dir(FsObject):
    
    def __init__(self, name, parent, children = []):
        super(Dir, self).__init__(name, parent)
        self.children = children

class File(FsObject):
    pass

class SshfsManager(object):

    def __init__(self, cfg):
        assert(isinstance(cfg, config_canonical.Config.SshfsManagerConfig))
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

    class DirWalker(object):

        def __init__(self, path):
            self.path, self.dirs, self.files = os.walk(path).next()

    def __init__(self, cfg, sshfs_access):
        assert(isinstance(cfg, config_canonical.Config.CacheManagerConfig))
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

    def list_dir(self, rel_path):
        assert(self.sshfs_access.is_serving())
        path_to_cache = self._get_cache_path(rel_path)
        if not path_to_cache:
            walker = self._create_dir_walker(self._absolute_remote_path(rel_path))
            # TODO: store internally dir structure
            return walker.dirs + walker.files

    def _create_dir_walker(self, path):
        return CacheManager.DirWalker(path)

    # getattr FS API equivalent
    def is_dir(self, path):
        st_mode = os.stat(self._absolute_remote_path(path)).st_mode
        return stat.S_ISDIR(st_mode) 

    def is_file(self, path):
        st_mode = os.stat(self._absolute_remote_path(path)).st_mode
        return stat.S_ISREG(st_mode) 

    # access FS API equivalent
    def exists(self, rel_path):
        if not self.sshfs_access.is_serving():
            return False
        # TODO: optimize, firstly cache dir
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
        self.st_blksize = 1
        self.st_rdev = 1
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
        self.st_blocks = 0

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
        self.cfg = cfg
        self.sshfs_mgr = SshfsManager(self.cfg.ssh)
        self.cache_mgr = CacheManager(self.cfg.cacheManager, 
                                           SshCacheFs.SshfsAccess(self.sshfs_mgr))
        self.root = Dir('/', None)

    def run(self):
        #self._sshfs_manager.run()
        #self._cache_manager.run()
        self.main()

    def stop(self):
        #self._sshfs_manager.stop()
        pass

    def fsinit(self):
        self.root_dir = Dir('/', stat.S_IFDIR|0755, os.getuid(), os.getgid())
        pass

    def fsdestroy(self):
        logging.info("Unmounting file system")

    def statfs(self):
        logging.info("statfs")
        stats = fuse.StatVfs()
        # Fill it in here. All fields take on a default value of 0.
        return stats

    def getattr(self, path):
        if (self.cache_mgr.is_dir(path)):
            # dr-xr-xr-x
            return Stat(stat.S_IFDIR | 0555, Stat.DIRSIZE, 1, os.getuid(), os.getgid())
        elif (self.cache_mgr.is_file(path)):
            # lr-xr-xr-x
            return Stat(stat.S_IFLNK | 0555, 0, 1, os.getuid(), os.getgid())
        else:
            return -errno.ENOENT
        
    def access(self, path, flags):
        logging.info("access: %s (flags %s)" % (path, oct(flags)))
        logging.info(flags & os.F_OK)
        if flags == os.F_OK:
            if self.cache_mgr.exists(path):
                return 0
            else:
                return -errno.EACCES

        if flags & os.W_OK:
            return -errno.EACCES

        # else if os.R_OK, os.X_OK, os.R_OK | os.X_OK:
        return 0

    def readlink(self, path):
        logging.info("readlink: %s" % path)
        return -errno.EOPNOTSUPP

    def mknod(self, path, mode, rdev):
        logging.info("mknod: %s" % path)
        return -errno.ENOENT

    def mkdir(self, path, mode):
        logging.info("mkdir: %s" % path)
        return -errno.ENOENT

    def unlink(self, path):
        logging.info("unlink: %s" % path)
        return -errno.ENOENT

    def rmdir(self, path):
        """Deletes a directory."""
        logging.info("rmdir: %s" % path)
        return -errno.ENOENT
        
    def symlink(self, target, name):
        logging.info("symlink: target %s, name: %s" % (target, name))
        return -errno.EOPNOTSUPP

    def link(self, target, name):
        logging.info("link: target %s, name: %s" % (target, name))
        return -errno.EOPNOTSUPP

    def rename(self, old, new):
        logging.info("rename: target %s, name: %s" % (old, new))
        return -errno.EOPNOTSUPP

    def chmod(self, path, mode):
        logging.info("chmod: %s (mode %s)" % (path, oct(mode)))
        return -errno.EOPNOTSUPP

    def chown(self, path, uid, gid):
        logging.info("chown: %s (uid %s, gid %s)" % (path, uid, gid))
        return -errno.EOPNOTSUPP

    def truncate(self, path, size):
        """
        Shrink or expand a file to a given size.
        If 'size' is smaller than the existing file size, truncate it from the
        end.
        If 'size' if larger than the existing file size, extend it with null
        bytes.
        """
        logging.info("truncate: %s (size %s)" % (path, size))
        return 0

    ### DIRECTORY OPERATION METHODS ###
    # Methods in this section are operations for opening directories and
    # working on open directories.
    # "opendir" is the method for opening directories. It *may* return an
    # arbitrary Python object (not None or int), which is used as a dir
    # handle by the methods for working on directories.
    # All the other methods (readdir, fsyncdir, releasedir) are methods for
    # working on directories. They should all be prepared to accept an
    # optional dir-handle argument, which is whatever object "opendir"
    # returned.

    def opendir(self, path):
        """
        Checks permissions for listing a directory.
        This should check the 'r' (read) permission on the directory.

        On success, *may* return an arbitrary Python object, which will be
        used as the "fh" argument to all the directory operation methods on
        the directory. Or, may just return None on success.
        On failure, should return a negative errno code.
        Should return -errno.EACCES if disallowed.
        """
        logging.info("opendir: %s" % path)
        return self.root
        #return -errno.EACCES

    def releasedir(self, path, dh):
        logging.info("releasedir: %s (dh %s)" % (path, dh))

    def fsyncdir(self, path, datasync, dh):
        logging.info("fsyncdir: %s (datasync %s, dh %s)"
            % (path, datasync, dh))

    def readdir(self, path, offset = None, dh = None):
        """
        Generator function. Produces a directory listing.
        Yields individual fuse.Direntry objects, one per file in the
        directory. Should always yield at least "." and "..".
        Should yield nothing if the file is not a directory or does not exist.
        (Does not need to raise an error).

        offset: I don't know what this does, but I think it allows the OS to
        request starting the listing partway through (which I clearly don't
        yet support). Seems to always be 0 anyway.
        """
        logging.info("readdir: %s (offset %s, dh %s)" % (path, offset, dh))
        # Update timestamps: readdir updates atime
        if not self.cache_mgr.exists(path):
            yield 
        elif not self.cache_mgr.is_dir(path):
            yield

        yield fuse.Direntry(".")
        yield fuse.Direntry("..")
        for entry in self.cache_mgr.list_dir(path):
            yield fuse.Direntry(entry)

    ### FILE OPERATION METHODS ###
    # Methods in this section are operations for opening files and working on
    # open files.
    # "open" and "create" are methods for opening files. They *may* return an
    # arbitrary Python object (not None or int), which is used as a file
    # handle by the methods for working on files.
    # All the other methods (fgetattr, release, read, write, fsync, flush,
    # ftruncate and lock) are methods for working on files. They should all be
    # prepared to accept an optional file-handle argument, which is whatever
    # object "open" or "create" returned.

    def open(self, path, flags):
        logging.info("open: %s (flags %s)" % (path, oct(flags)))
        #return -errno.ENOENT
        #file = self._search_path(path)
        #if file is None:
            #return -errno.ENOENT
        #if not isinstance(file, File):
            #return -errno.EISDIR
        #accessflags = 0
        #if flags & os.O_RDONLY:
            #accessflags |= os.R_OK
        #if flags & os.O_WRONLY:
            #accessflags |= os.W_OK
        #if flags & os.O_RDWR:
            #accessflags |= os.R_OK | os.W_OK
        #if file.stat.check_permission(self.GetContext()['uid'],
            #self.GetContext()['gid'], accessflags):
            #return file
        #else:
            #return -errno.EACCES

    def fgetattr(self, path, fh):
        logging.debug("fgetattr: %s (fh %s)" % (path, fh))
        return fh.stat

    def release(self, path, flags, fh):
        logging.info("release: %s (flags %s, fh %s)" % (path, oct(flags), fh))

    def fsync(self, path, datasync, fh):
        logging.info("fsync: %s (datasync %s, fh %s)" % (path, datasync, fh))

    def flush(self, path, fh):
        logging.info("flush: %s (fh %s)" % (path, fh))

    def read(self, path, size, offset, fh):
        logging.info("read: %s (size %s, offset %s, fh %s)"
            % (path, size, offset, fh))
        return fh.read(size, offset)

    def write(self, path, buf, offset, fh):
        logging.info("write: %s (offset %s, fh %s)" % (path, offset, fh))
        logging.debug("  buf: %r" % buf)
        return fh.write(buf, offset)

    def ftruncate(self, path, size, fh):
        logging.info("ftruncate: %s (size %s, fh %s)" % (path, size, fh))
        fh.truncate(size)

def main():
    usage = """
    SshCacheFs: Sshfs read-only cache virtual filesystem.
    """ + fuse.Fuse.fusage
    server = SshCacheFs(config.getConfig(),
                        version="%prog " + fuse.__version__,
                        usage=usage,
                        dash_s_do='setsingle')

    #server.flags = 0
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
