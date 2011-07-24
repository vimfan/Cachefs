import time

from loclogger import DEBUG

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
            if entry.timestamp - time.time() > 60: # TODO: parametrize this
                return None
            return entry
        return None

    def cache_attributes(self, path, st = None):
        self._getattr[path] = MemoryCache.GetattrEntry(st, time.time())

    def cache_link_target(self, path, target):
        self._readlink[path] = MemoryCache.ReadlinkEntry(target, time.time())
