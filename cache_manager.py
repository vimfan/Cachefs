from loclogger import DEBUG, INFO, ERROR, trace
import loclogger 

import stat
import errno
import shutil

from memory_cache import MemoryCache
import memory_cache # ugly

import os
import path_factory
import disk_cache

class CacheManager(object):
       
    def __init__(self, cfg):
        self._cfg = cfg
        self._memoryCache = MemoryCache(self._cfg.memory_cache_lifetime)
        self._diskCache = disk_cache.DiskCache(self._cfg, self._memoryCache)
        self._prepare_directories()

    @trace
    def getAttributes(self, path, pathToCache=False):
        memstat = self._memoryCache.getAttributes(path)

        if not memstat:
            DEBUG("Checking cache directory for %s" % path)
            st = self._getAttributesFromDiskCache(path)
            self._memoryCache.cacheAttributes(path, st)
            memstat = self._memoryCache.getAttributes(path)

        return memstat.stat

    @trace
    def listDirectory(self, path):
        # FIXME: do it with try catch
        try:
            return self._memoryCache.listDirectory(path)
        except memory_cache.MemoryCacheNotValid, e:
            DEBUG("Memory cache is not valid")
            return self._diskCache.listDirectory(path)

    @trace
    def getPathToCachedFile(self, path):
        return self._diskCache.getPathToCachedFile(path)

    @trace
    def readLink(self, filepath):
        target_entry = self._memoryCache.readLink(filepath)
        if not target_entry or not target_entry.target:
            readLink = self._diskCache.readLink(filepath)
            self._memoryCache.cacheLinkTarget(filepath, readLink)
            target_entry = self._memoryCache.readLink(filepath)
        return target_entry.target


    @trace
    def isDirectory(self, path):
        memstat = self._memoryCache.getAttributes(path)
        if memstat:
            if memstat.stat:
                return stat.S_ISDIR(memstat.stat.st_mode)
            if not memstat.stat:
                return False

        return self._diskCache.isDirectory(path)

    @trace
    def isExisting(self, path):
        fileExists = self._memoryCache.isExisting(path)
        if not fileExists is None:
            return fileExists
        return self._diskCache.isExisting(path)

    def _getAttributesFromDiskCache(self, path):

        try:

            st = self._diskCache.getAttributes(path)
            if (not st is None 
                and stat.S_ISDIR(st.st_mode)):
                self._diskCache.cacheDirectory(path)
            return st

        except disk_cache.ParentDirNotCached, e:

            DEBUG("Needs to cache directory: %s" % path)
            self._diskCache.cacheDirectory(os.path.dirname(path))
            return self._getAttributesFromDiskCache(path)

        except disk_cache.OriginFileNotExists, e:

            DEBUG("File doesn't exist %s" % path)
            return None


    def _prepare_directories(self):
        dir = self._cfg.cache_root_dir
        if not os.path.exists(dir):
            os.makedirs(dir)

