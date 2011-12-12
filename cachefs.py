#!/usr/bin/env python

import os
import shutil
import signal
import stat
import subprocess
import sys
import datetime
import calendar
import errno
import stat    # for file properties
import os      # for filesystem modes (O_RDONLY, etc)
import fuse
import traceback
import string
import loclogger
from loclogger import DEBUG, INFO, ERROR, trace
from memory_cache import MemoryCache
import memory_cache # ugly
from file import File

from cache_manager import CacheManager

import config as config_canonical

time = None

# FUSE version at the time of writing. Be compatible with this version.
fuse.fuse_python_api = (0, 2)


class CacheFs(fuse.Fuse):

    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)
        self.cfg = None
        self.cacheManager = None
        self.filebuffer = None

    def run(self):
        self.cacheManager = CacheManager(self.cfg.cache_manager)
        self.main()

    def stop(self):
        pass

    def parse(self, *args, **kw):
        '''This method shall be moved somewhere in config module'''
        fuse_args = super(CacheFs, self).parse(*args, **kw)
        if fuse_args.modifiers['showhelp']:
            # not beautiful, but works
            sys.exit(0) 

        self.cfg = config_canonical.getConfig()

        options, arguments =  self.cmdline

        loclogger.initialize(options.log_path)
        
        if options.debug:
            loclogger.enableDebug()

        self.cfg.parse(options, arguments, self.fuse_args.mountpoint)

    @trace
    def fsinit(self):
        INFO("Initializing file system")

    @trace
    def fsdestroy(self):
        self.stop()
        INFO("Unmounting file system")

    @trace
    def statfs(self):
        stats = fuse.StatVfs()
        return stats

    @trace
    def getattr(self, path):
        st = self.cacheManager.getAttributes(path)
        if not st:
            return -errno.ENOENT
        return st

    @trace
    def access(self, path, flags):
        if flags == os.F_OK:
            if self.cacheManager.isExisting(path):
                return 0
            else:
                return -errno.EACCES
        if flags & os.W_OK:
            return -errno.EACCES
        return 0

    @trace
    def readlink(self, path):
        pathToCachedFile = self.cacheManager.readLink(path)
        if pathToCachedFile:
            return pathToCachedFile
        return -errno.ENOENT

    @trace
    def opendir(self, path):
        if not (self.cacheManager.isExisting(path) and self.cacheManager.isDirectory(path)):
            return -errno.ENOENT
        return None # success

    @trace
    def readdir(self, path, offset = None, dh = None):
        # TODO: Update timestamps: readdir updates atime
        if not self.cacheManager.isExisting(path):
            yield
        elif not self.cacheManager.isDirectory(path):
            yield

        yield fuse.Direntry(".")
        yield fuse.Direntry("..")
        for entry in self.cacheManager.listDirectory(path):
            yield fuse.Direntry(entry)

    @trace
    def read(self, path, size, offset, fh):
        if fh.lseek != offset:
            os.lseek(fh.fh, offset, 0)
        self.filebuffer = os.read(fh.fh, size)
        fh.lseek = offset + size
        return self.filebuffer

    @trace
    def open(self, path, flags):
        st = self.cacheManager.getAttributes(path)
        if st:
            cache_path = self.cacheManager.getPathToCachedFile(path)
            return File(os.open(cache_path, flags), os.path.basename(path), st)

    @trace
    def release(self, path, flags, fh):
        os.close(fh.fh)

    @trace
    def fgetattr(self, path, fh):
        return fh.stat

    @trace
    def fsync(self, path, datasync, fh):
        pass

    @trace
    def flush(self, path, fh):
        pass

    @trace
    def mknod(self, path, mode, rdev):
        return -errno.ENOENT

    @trace
    def mkdir(self, path, mode):
        return -errno.ENOENT

    @trace
    def unlink(self, path):
        return -errno.ENOENT

    @trace
    def rmdir(self, path):
        return -errno.ENOENT
        
    @trace
    def symlink(self, target, name):
        return -errno.EOPNOTSUPP

    @trace
    def link(self, target, name):
        return -errno.EOPNOTSUPP

    @trace
    def rename(self, old, new):
        return -errno.EOPNOTSUPP

    @trace
    def chmod(self, path, mode):
        return -errno.EOPNOTSUPP

    @trace
    def chown(self, path, uid, gid):
        return -errno.EOPNOTSUPP

    @trace
    def truncate(self, path, size):
        return 0

    @trace
    def releasedir(self, path, dh = None):
        pass

    @trace
    def fsyncdir(self, path, datasync, dh):
        pass

    @trace
    def write(self, path, buf, offset, fh):
        return -errno.EOPNOTSUPP

    @trace
    def ftruncate(self, path, size, fh):
        fh.truncate(size)

def main():
    usage = """
    CacheFs: Read-only cache virtual filesystem.
    """ + fuse.Fuse.fusage
    server = CacheFs(version="%prog " + fuse.__version__,
                     usage=usage,
                     dash_s_do='setsingle')

    server.parser.add_option('-x', '--source-dir', 
                             dest="source_dir", 
                             help="Source directory which will be cached",
                             metavar="MANDATORY_SOURCE_DIR_PATH",
                             type="str")

    server.parser.add_option('-c', '--cache-dir',
                             dest='cache_dir',
                             help="Path to directory with cache (will be created if not exists)",
                             metavar="MANDATORY_EXISTING_CACHE_DIR_PATH",
                             type="str")

    server.parser.add_option('--disk-cache-lifetime',
                             dest="disk_cache_lifetime", 
                             help="Long time stamp lifetime in seconds. (default: 600)", 
                             metavar="TIME_IN_SECONDS", 
                             type="int",
                             default=600)

    server.parser.add_option('--memory-cache-lifetime',
                             dest="memory_cache_lifetime", 
                             help="Short time stamp lifetime in seconds. (default: 60)", 
                             metavar="TIME_IN_SECONDS",
                             type="int",
                             default=60)

    server.parser.add_option('--debug',
                             dest="debug",
                             help="Enable more verbose logging",
                             action="store_true",
                             default=False)

    server.parser.add_option('-l', '--log',
                             dest="log_path",
                             help="Path to log file",
                             metavar='LOG_FILE',
                             type="str",
                             default="logs/LOG")

    server.flags = 0
    server.multithreaded = 0
    try:
        server.parse(errex=1)
        server.run()
    except fuse.FuseError, e:
        print str(e)
    except config_canonical.ConfigValidator.ConfigError, e:
        print "\nError: {error} \n".format(error = str(e.msg))
        server.parser.print_help()

if __name__ == '__main__': 
    time_stubbed = False
    try:
        # testing environment with mocked time module
        import mocks.time_mock # file available in tests directory
        time = mocks.time_mock.ModuleInterface()
        memory_cache.time = time
        time_stubbed = True

    except Exception, e:
        # standard environment
        import time as time_module
        time = time_module
        memory_cache.time = time_module
        time_stubbed = False

    try:
        if time_stubbed:
            time.timeMock.initialize()

        main()

    except Exception, e:
        print(str(e))

    finally:
        if time_stubbed:
            time.timeMock.dispose()

    DEBUG("time stubbed: " + str(time_stubbed))
    INFO("File system unmounted")
else:
    import time as time_module
    time = time_module
