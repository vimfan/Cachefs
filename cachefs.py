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
import fuse
import traceback

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


# FUSE version at the time of writing. Be compatible with this version.
fuse.fuse_python_api = (0, 2)

if not os.path.exists("logs"):
    os.makedirs("logs")

LOG_FILENAME = "logs/LOG%s" % os.getpid()
#LOG_FILENAME='/dev/null'

if os.path.exists(LOG_FILENAME):
    os.remove(LOG_FILENAME)

logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,)

if os.path.lexists("LOG"):
    os.unlink("LOG")

os.symlink(LOG_FILENAME, "LOG")

def NO_LOG(msg):
    pass

def DEBUG(msg):
    logging.debug(msg)

def INFO(msg):
    logging.info(msg)

def ERROR(msg):
    logging.error(msg)

#ERROR, DEBUG, INFO = NO_LOG, NO_LOG, NO_LOG

depth = 0
def method_logger(f):
    def wrapper(*args, **kw):
        global depth
        try:
            class_name = args[0].__class__.__name__
            func_name = f.func_name
            depth += 1
            DEBUG("%s:%s {%s- %s.%s(args: %s, kw: %s)" %
                          (f.func_code.co_filename,
                           f.func_code.co_firstlineno,
                           depth,
                           class_name, func_name,
                           args[1:], kw))
            retval = f(*args, **kw)
            DEBUG("%s:%s -%s} %s.%s(...) -> returns: %s(%r)" %
                          (f.func_code.co_filename,
                           f.func_code.co_firstlineno,
                           depth,
                           class_name, func_name, type(retval), retval))
            depth -= 1
            return retval
        except Exception, inst:
            ERROR("function: %s, exception: %r" % (f.func_name, inst))
            exc_traceback = traceback.format_exc()
            ERROR("Exception traceback: %s" % exc_traceback)
            raise inst
    return wrapper

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

class MemoryCache(object):

    class GetattrEntry:

        def __init__(self, st, stamp = None):
            self.stat = st
            self.timestamp = stamp

    class ReadlinkEntry:
        
        def __init__(self, target, stamp = None):
            self.target = target
            self.timestamp = stamp

    def __init__(self):
        self._getattr = {}
        self._readlink = {}

    def get_attributes(self, path):
        DEBUG("MEMORY CACHED_FILE ATTRIBUTES: %s" % len(self._getattr))
        if self._getattr.has_key(path):
            entry = self._getattr[path]
            if entry.timestamp - time.time() > 60:
                return None
            return entry
        return None

    def read_link(self, path):
        DEBUG("MEMORY CACHED TARGET LINKS: %s" % len(self._readlink))
        if self._readlink.has_key(path):
            entry = self._readlink[path]
            if entry.timestamp - time.time() > 60:
                return None
            return entry
        return None

    def cache_attributes(self, path, st = None):
        self._getattr[path] = MemoryCache.GetattrEntry(st, time.time())

    def cache_link_target(self, path, target):
        self._readlink[path] = MemoryCache.ReadlinkEntry(target, time.time())

class CacheManager(object):

    class DirWalker(object):

        @staticmethod
        def walk(dirpath):
            dirs, files, links = [], [], []
            for entry in os.listdir(dirpath):
                try:
                    full_path = os.sep.join([dirpath, entry])
                    st_mode = os.lstat(full_path).st_mode
                    if stat.S_ISREG(st_mode):
                        files.append(entry)
                    elif stat.S_ISDIR(st_mode):
                        dirs.append(entry)
                    elif stat.S_ISLNK(st_mode):
                        links.append(entry)
                    else:
                        DEBUG("unsupported type of file %s" % full_path)
                except OSError:
                    DEBUG("cannot stat: %s" % full_path)

            return dirs, files, links

        def __init__(self, dirpath):
            '''For given directory path get: subdirs, files, links in the dir'''
            self.dirs, self.files, self.links = CacheManager.DirWalker.walk(dirpath)
            
    class PathTransformer(object):

        FILE_SUFFIX = 'filecache'
        DIR_SUFFIX = 'dircache'
 
        def transform_filepath(self, filepath):
            return '.'.join([filepath, CacheManager.PathTransformer.FILE_SUFFIX])

        def reverse_transform_filepath(self, filepath):
            if filepath.endswith(CacheManager.PathTransformer.FILE_SUFFIX):
                return filepath[:-(len(CacheManager.PathTransformer.FILE_SUFFIX) + 1)]
            return filepath

        def transform_dirpath(self, dirpath):
            return '.'.join([dirpath, CacheManager.PathTransformer.DIR_SUFFIX])

        def reverse_transform_dirpath(self, dirpath):
            if dirpath.endswith(CacheManager.PathTransformer.DIR_SUFFIX):
                return dirpath[:-(len(CacheManager.PathTransformer.DIR_SUFFIX) + 1)]
            return dirpath

    class CachedDirWalker(object):

        INITIALIZATION_STAMP = '.cache_initialized'

        def __init__(self, path):
            self._dirs, self._files, self._links = CacheManager.DirWalker.walk(path)
            self.path_transformer = CacheManager.PathTransformer()

        @property
        def files(self):
            stamp = CacheManager.CachedDirWalker.INITIALIZATION_STAMP
            if self._links.count(stamp):
                self._links.remove(stamp)
            all_files = self._files + list(set(self._links) - set(self.links))
            return list(set(([
                self.path_transformer.reverse_transform_filepath(filename) 
                for filename in all_files])))

        @property
        def dirs(self):
            stamp = CacheManager.CachedDirWalker.INITIALIZATION_STAMP
            if self._dirs.count(stamp):
                self._dirs.remove(stamp)
            return list(set(([
                self.path_transformer.reverse_transform_dirpath(dirname) for dirname in self._dirs
                ])))

        @property
        def links(self):
            return filter(lambda link: not link.endswith(CacheManager.PathTransformer.FILE_SUFFIX),
                          self._links)

       
    def __init__(self, cfg):
        assert(isinstance(cfg, config_canonical.Config.CacheManagerConfig))
        self.cfg = cfg
        self.path_transformer = CacheManager.PathTransformer()
        self.memcache = MemoryCache()

    @method_logger
    def run(self):
        self._prepare_directories()

    @method_logger
    def stop(self):
        # deliberately don't remove any directories
        pass

    def _read_link(self, rel_filepath):
        cache_filepath = self._get_path_to_cached_file(rel_filepath)
        if cache_filepath and os.path.islink(cache_filepath):
            return os.readlink(cache_filepath)
        if not cache_filepath:
            self._create_local_copy(rel_filepath)
            cache_filepath = self._get_path_to_cached_file(rel_filepath)
            assert(cache_filepath)

        if os.path.islink(cache_filepath):
            return os.readlink(cache_filepath)
        else:
            return cache_filepath

    @method_logger
    def read_link(self, rel_filepath):
        target_entry = self.memcache.read_link(rel_filepath)
        if not target_entry:
            self.memcache.cache_link_target(rel_filepath, self._read_link(rel_filepath))
            target_entry = self.memcache.read_link(rel_filepath)
        return target_entry.target

    @method_logger
    def list_dir(self, rel_path):
        path_to_cache = self._get_path_to_cached_file(rel_path)
        cache_walker = self._create_cached_dir_walker(path_to_cache)
        return cache_walker.files + cache_walker.dirs + cache_walker.links

    @method_logger
    def get_attributes(self, relative_path):
        memstat = self.memcache.get_attributes(relative_path)
        if not memstat:
            self.memcache.cache_attributes(relative_path, self._get_attributes(relative_path))
            memstat = self.memcache.get_attributes(relative_path)
        return memstat.stat

    def _get_attributes(self, relative_path):
        try:
            path_to_cache = self._cache_path(relative_path)
            st = os.lstat(path_to_cache)
            if stat.S_ISREG(st.st_mode):
                return Stat(stat.S_IFLNK | 0755, 0, 1, os.getuid(), os.getgid())
            elif stat.S_ISLNK(st.st_mode):
                return st
            else:
                if not self._has_init_stamp(relative_path):
                    try:
                        self._cache_directory(relative_path)
                    except:
                        DEBUG("OOPS")
                return st
        except OSError, ex:
            DEBUG(ex)
            path_dir = os.path.dirname(relative_path)
            has_stamp = self._has_init_stamp(path_dir)
            if has_stamp:
                filepath = self.path_transformer.transform_filepath(path_to_cache)
                if os.path.lexists(filepath):
                    return Stat(stat.S_IFLNK | 0777, 0, 1, os.getuid(), os.getgid())
                try:
                    dirpath = self.path_transformer.transform_dirpath(path_to_cache)
                    if os.path.exists(dirpath):
                        self._cache_directory(relative_path)
                        return os.lstat(path_to_cache)
                    else:
                        return None
                except OSError, ex:
                    DEBUG(ex)
                    return None
            else:
                try:
                    path_to_remote = self._absolute_remote_path(relative_path)
                    st = os.lstat(path_to_remote)
                    assert(stat.S_ISDIR(st.st_mode))
                    self._cache_directory(relative_path)
                except OSError, ex:
                    DEBUG(ex)
                    return None

    @method_logger
    def _cache_directory(self, rel_path):
        remote_path = self._absolute_remote_path(rel_path)
        assert(os.path.isdir(remote_path))

        path_to_cache = self._cache_path(rel_path)
        try:
            os.mkdir(path_to_cache)
        except OSError:
            DEBUG("most likely directory %s already exists" % path_to_cache)

        cache_walker = self._create_cached_dir_walker(path_to_cache)
        remote_dir_walker = self._create_dir_walker(remote_path)
        DEBUG("REMOTE PATH: %s" % remote_path)

        not_cached_files = list(set(remote_dir_walker.files) - set(cache_walker.files))
        DEBUG("NOT CACHED FILES %s" % not_cached_files)

        not_cached_dirs = list(set(remote_dir_walker.dirs) - set(cache_walker.dirs))
        DEBUG("NOT CACHED DIRS %s" % not_cached_dirs)

        not_cached_links = list(set(remote_dir_walker.links) - set(cache_walker.links))
        DEBUG("NOT CACHED LINKS %s" % not_cached_links)

        for filename in not_cached_files:
            transformed_filepath = self.path_transformer.transform_filepath(filename)
            os.symlink(filename, os.sep.join([path_to_cache, transformed_filepath]))

        for dirname in not_cached_dirs:
            transformed_dirpath = self.path_transformer.transform_dirpath(dirname)
            os.mkdir(os.sep.join([path_to_cache,transformed_dirpath]))

        for link in not_cached_links:
            link_target = os.readlink(os.sep.join([remote_path, link]))
            os.symlink(link_target, os.sep.join([path_to_cache, link]))

        dir_cache_stamp = self.path_transformer.transform_dirpath(path_to_cache)
        if os.path.lexists(dir_cache_stamp):
            os.rmdir(dir_cache_stamp)

        self._create_dir_init_stamp(rel_path)

    @method_logger
    def _create_cache_stamp(self, path_to_cache, st_mode):
        if stat.S_ISDIR(st_mode):
            if not os.path.exists(path_to_cache):
                os.makedirs(path_to_cache, st_mode)
            return
        elif stat.S_ISREG(st_mode):
            stamp = self.path_transformer.transform_filepath(path_to_cache)
            if not os.path.lexists(stamp):
                os.symlink('#', stamp)
            return
        else:
            DEBUG("Don't know how to create cache stamp for '%s'" % path_to_cache)
            return
               
    @method_logger
    def is_dir(self, rel_path):
        memstat = self.memcache.get_attributes(rel_path)
        if memstat:
            if memstat.stat:
                return stat.S_ISDIR(memstat.stat.st_mode)
            if not memstat.stat:
                return False
        cached_path = self._cache_path(rel_path)
        if os.path.lexists(cached_path):
            return os.path.isdir(cached_path)
        dirpath = os.path.dirname(cached_path)
        if self._has_init_stamp(dirpath):
            transformed_path = self.path_transformer.transform_dirpath(cached_path)
            return (os.path.exists(cached_path) or os.path.exists(transformed_path))
        return os.path.isdir(self._absolute_remote_path(rel_path))

    @method_logger
    def exists(self, rel_path):
        memstat = self.memcache.get_attributes(rel_path)
        if memstat:
            return memstat.stat <> None
        cached_path = self._cache_path(rel_path)
        if os.path.lexists(cached_path):
            return True
        dirpath = os.path.dirname(rel_path)
        if self._has_init_stamp(dirpath):
            filepath_transformed = self.path_transformer.transform_filepath(cached_path)
            return os.path.lexists(filepath_transformed)
        remote_path = self._absolute_remote_path(rel_path)
        return os.path.lexists(remote_path)

    @method_logger
    def _create_dir_init_stamp(self, rel_dirpath):
        os.symlink('.', self._get_init_stamp(rel_dirpath))

    @method_logger
    def _remove_dir_init_stamp(self, rel_dirpath):
        os.unlink(self._get_init_stamp(rel_dirpath))

    @method_logger
    def _has_init_stamp(self, rel_dirpath):
        return os.path.lexists(self._get_init_stamp(rel_dirpath))

    def _get_init_stamp(self, rel_dirpath):
        return os.sep.join([self._cache_path(rel_dirpath), 
                            CacheManager.CachedDirWalker.INITIALIZATION_STAMP])

    def _create_file_stamp(self, rel_filepath):
        path_to_cache = self._cache_path(rel_filepath)
        stamp = self.path_transformer.transform_filepath(path_to_cache)
        if not os.path.lexists(stamp):
            os.symlink('#', stamp)

    def _remove_file_stamp(self, rel_filepath):
        path_to_cache = self._cache_path(rel_filepath)
        stamp = self.path_transformer.transform_filepath(path_to_cache)
        if not os.path.lexists(stamp):
            os.unlink(stamp)

    def _create_dir_walker(self, path):
        return CacheManager.DirWalker(path)

    def _create_cached_dir_walker(self, path):
        return CacheManager.CachedDirWalker(path)

    def _create_local_copy(self, rel_filepath):
        src = os.sep.join([self.cfg.source_dir, rel_filepath])
        dst = self._cache_path(rel_filepath)
        stamp = self.path_transformer.transform_filepath(dst)
        parent_dir = os.path.dirname(dst)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        if os.path.islink(src):
            link_target = os.readlink(src)
            os.symlink(link_target, dst)
        else:
            shutil.copyfile(src, dst)
            shutil.copymode(src, dst)
        if os.path.lexists(stamp):
            os.unlink(stamp)

    def _get_path_to_cached_file(self, rel_filepath):
        full_path = self._cache_path(rel_filepath)
        if os.path.lexists(full_path):
            return full_path
        return None

    def _cache_path(self, rel_filepath):
        root = self._cache_root_dir()
        return "".join([root, rel_filepath])

    def _absolute_remote_path(self, rel_path):
        path = "".join([self.cfg.source_dir, rel_path])
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

class SshCacheFs(fuse.Fuse):

    def __init__(self, cfg, *args, **kw):
        #super(SshCacheFs, self).__init__(*args, **kwargs)
        fuse.Fuse.__init__(self, *args, **kw)
        self.cfg = cfg
        self.cache_mgr = CacheManager(self.cfg.cache_manager)
        self.root = Dir('/', None)

    @method_logger
    def run(self):
        self.cache_mgr.run()
        self.main()

    @method_logger
    def stop(self):
        self.cache_mgr.stop()

    @method_logger
    def fsinit(self):
        INFO("Initializing file system")

    @method_logger
    def fsdestroy(self):
        self.stop()
        INFO("Unmounting file system")

    @method_logger
    def statfs(self):
        stats = fuse.StatVfs()
        # Fill it in here. All fields take on a default value of 0.
        return stats

    @method_logger
    def getattr(self, path):
        assert(type(path) == str)
        st = self.cache_mgr.get_attributes(path)
        if not st:
            return -errno.ENOENT
        return st

    @method_logger
    def access(self, path, flags):
        if flags == os.F_OK:
            if self.cache_mgr.exists(path):
                return 0
            else:
                return -errno.EACCES

        if flags & os.W_OK:
            return -errno.EACCES

        # else if os.R_OK, os.X_OK, os.R_OK | os.X_OK:
        return 0

    @method_logger
    def readlink(self, path):
        path_to_cached_file = self.cache_mgr.read_link(path)
        if path_to_cached_file:
            return path_to_cached_file
        return -errno.ENOENT

    @method_logger
    def mknod(self, path, mode, rdev):
        return -errno.ENOENT

    @method_logger
    def mkdir(self, path, mode):
        return -errno.ENOENT

    @method_logger
    def unlink(self, path):
        return -errno.ENOENT

    @method_logger
    def rmdir(self, path):
        return -errno.ENOENT
        
    @method_logger
    def symlink(self, target, name):
        return -errno.EOPNOTSUPP

    @method_logger
    def link(self, target, name):
        return -errno.EOPNOTSUPP

    @method_logger
    def rename(self, old, new):
        return -errno.EOPNOTSUPP

    @method_logger
    def chmod(self, path, mode):
        return -errno.EOPNOTSUPP

    @method_logger
    def chown(self, path, uid, gid):
        return -errno.EOPNOTSUPP

    @method_logger
    def truncate(self, path, size):
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

    @method_logger
    def opendir(self, path):
        if not self.cache_mgr.exists(path):
            return -errno.ENOENT
        if not self.cache_mgr.is_dir(path):
            return -errno.ENOENT
        return None # means success

    @method_logger
    def releasedir(self, path, dh = None):
        pass

    @method_logger
    def fsyncdir(self, path, datasync, dh):
        pass

    @method_logger
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

    @method_logger
    def open(self, path, flags):
        pass
       
    @method_logger
    def fgetattr(self, path, fh):
        return fh.stat

    @method_logger
    def release(self, path, flags, fh):
        pass

    @method_logger
    def fsync(self, path, datasync, fh):
        pass

    @method_logger
    def flush(self, path, fh):
        pass

    @method_logger
    def read(self, path, size, offset, fh):
        return fh.read(size, offset)

    @method_logger
    def write(self, path, buf, offset, fh):
        return fh.write(buf, offset)

    @method_logger
    def ftruncate(self, path, size, fh):
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
        server.run()
    except fuse.FuseError, e:
        print str(e)

if __name__ == '__main__':
    main()
    INFO("File system unmounted")

