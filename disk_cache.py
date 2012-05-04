import loclogger
from loclogger import DEBUG, INFO, trace
import path_factory
import os
import shutil
import stat
import errno

class ParentDirNotCached(Exception):
    pass

class OriginFileNotExists(Exception):
    pass

class DiskCache(object):
    
    def __init__(self, config, memoryCache):
        self._config = config
        self._pathFactory = path_factory.PathFactory(self._config)
        self._memoryCache = memoryCache

    @trace
    def isDirectory(self, path):

        pathToCachedDir = self._pathFactory.createPathToDiskCache(path)
        if os.path.lexists(pathToCachedDir):
            return os.path.isdir(pathToCachedDir)

        dirpath = os.path.dirname(pathToCachedDir)
        if self._isDirectoryCached(dirpath):
            directoryMarker = self._pathFactory.createPathToDiskCacheDirectoryMarker(path)
            return (os.path.exists(pathToCachedDir) or os.path.exists(directoryMarker))

        return os.path.isdir(self._pathFactory.createAbsoluteSourcePath(path))

    @trace
    def exists(self, path):
        pathToCache = self._pathFactory.createPathToDiskCache(path)

        if os.path.lexists(pathToCache):
            return True

        dirpath = os.path.dirname(path)
        if self._isDirectoryCached(dirpath):
            fileMarker = self._pathFactory.createPathToDiskCacheFileMarker(path)
            return os.path.lexists(fileMarker)

        pathToSource = self._pathFactory.createAbsoluteSourcePath(path)
        return os.path.lexists(pathToSource)

    @trace
    def getAttributes(self, path):

        pathToDiskCache = self._pathFactory.createPathToDiskCache(path)

        try:

            return os.lstat(pathToDiskCache)

        except OSError, e:
            
            # FIXME: check errno

            if not self._isDirectoryCached(os.path.dirname(path)):
                # XXX: know it seems to be exceptional case when someone is messing up the disk cache
                # Might be a case when disk cache expriation will be implemented
                raise ParentDirNotCached()

            try:

                pathToSource = self._pathFactory.createAbsoluteSourcePath(path) 

                fileMarker = self._pathFactory.createPathToDiskCacheFileMarker(path)
                if os.path.lexists(fileMarker):
                    return os.lstat(pathToSource)

                directoryMarker = self._pathFactory.createPathToDiskCacheDirectoryMarker(path)
                if os.path.lexists(directoryMarker):
                    st = os.lstat(pathToSource)
                    self._cacheDirectory(path)
                    return st

                return None # file doesn't exists

            except OSError, e:

                 # FIXME: check errno
                 raise OriginFileNotExists()

    @trace
    def readLink(self, path):
        pathToCachedFile = self._getPathToCachedFile(path)

        if pathToCachedFile and os.path.islink(pathToCachedFile):
            return os.readlink(pathToCachedFile)

        if not pathToCachedFile:
            self._cacheFile(path)
            pathToCachedFile = self._getPathToCachedFile(path)

        if os.path.islink(pathToCachedFile):
            return os.readlink(pathToCachedFile)
        else:
            return pathToCachedFile

    @trace
    def listDirectory(self, path):
        pathToCache = self._pathFactory.createPathToDiskCache(path)

        try:

            cacheWalker = self._createCachedDirWalker(pathToCache)

        except OSError: 

            self.cacheDirectory(path)
            cacheWalker = self._createCachedDirWalker(pathToCache)

        return cacheWalker.files + cacheWalker.dirs + cacheWalker.links


    @trace
    def cacheDirectory(self, path):
        if not self._isDirectoryCached(path):
            return self._cacheDirectory(path)

    @trace
    def getPathToCachedFile(self, path):

        if self._getPathToCachedFile(path) is None:
            self._cacheFile(path)

        return self._pathFactory.createPathToDiskCache(path)

    def _getPathToCachedFile(self, path):
        fullPath = self._pathFactory.createPathToDiskCache(path)
        if os.path.lexists(fullPath):
            return fullPath
        return None

    def _isDirectoryCached(self, path):

        initStampPath = self._pathFactory.createPathInitializationMarker(
            path, CachedDirWalker.INITIALIZATION_STAMP)

        return os.path.lexists(initStampPath)

    def _cacheDirectory(self, path):
        sourcePath = self._pathFactory.createAbsoluteSourcePath(path)
        pathToCache = self._pathFactory.createPathToDiskCache(path)
        try:
            os.mkdir(pathToCache)
        except OSError, e:
            parent_path = os.path.dirname(path)
            if e.errno == errno.ENOENT and '/' <> parent_path:
                self._cacheDirectory(parent_path)
                os.mkdir(pathToCache)
            if loclogger.debug:
                DEBUG("most likely directory %s already exists" % pathToCache)

        cacheWalker = self._createCachedDirWalker(pathToCache)
        sourceDirWalker = self._createDirectoryWalker(self._config.source_dir, path)
        sourceDirWalker.initialize()

        notCachedFiles = list(set(sourceDirWalker.files) - set(cacheWalker.files))
        notCachedDirectories = list(set(sourceDirWalker.dirs) - set(cacheWalker.dirs))
        notCachedLinks = list(set(sourceDirWalker.links) - set(cacheWalker.links))

        if loclogger.debug:
            DEBUG("REMOTE PATH: %s" % sourcePath)
            DEBUG("Files to be cached: %s" % notCachedFiles)
            DEBUG("Directories to be cached: %s" % notCachedDirectories)
            DEBUG("Links to be cached: %s" % notCachedLinks)

        for filename in notCachedFiles:
            fileMarker = self._pathFactory.createPathToDiskCacheFileMarker(os.path.join(path, filename))
            os.symlink(filename, fileMarker)

        for dirname in notCachedDirectories:
            directoryMarker = self._pathFactory.createPathToDiskCacheDirectoryMarker(os.path.join(path, dirname))
            os.mkdir(directoryMarker)

        for link in notCachedLinks:
            link_target = os.readlink(os.sep.join([sourcePath, link]))
            os.symlink(link_target, os.sep.join([pathToCache, link]))

        self._markDirectoryAsInitialized(path)


    def _markDirectoryAsInitialized(self, path):

        dir_cache_stamp = self._pathFactory.createPathToDiskCacheDirectoryMarker(os.path.dirname(path))
        try:
            os.rmdir(dir_cache_stamp)
        except:
            pass
        self._createDirectoryInitMarker(path)
        self._memoryCache.markAsChildrenCached(path, True)


    @trace
    def _cacheFile(self, path):

        src = os.sep.join([self._config.source_dir, path])
        dst = self._pathFactory.createPathToDiskCache(path)
        parent_dir = os.path.dirname(dst)

        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        if os.path.islink(src):
            link_target = os.readlink(src)
            os.symlink(link_target, dst)
        else:
            shutil.copyfile(src, dst)
            shutil.copymode(src, dst)

        stamp = self._pathFactory.createPathToDiskCacheFileMarker(path)
        if os.path.lexists(stamp):
            os.unlink(stamp)

    @trace
    def _createDirectoryInitMarker(self, dirpath):
        stamp_path = self._pathFactory.createPathInitializationMarker(
            dirpath, CachedDirWalker.INITIALIZATION_STAMP)
        os.symlink('.', stamp_path)

    def _createCachedDirWalker(self, path):
        return CachedDirWalker(path)

    def _createDirectoryWalker(self, rootpath, path):
        return DirWalker(rootpath, path, self._memoryCache)

    '''
    def _removeDirectoryInitMarker(self, dirpath):
        os.unlink(self._get_init_stamp(dirpath))

    def _create_file_stamp(self, filepath):
        pathToCache = self._cache_path(filepath)
        stamp = self._pathTransformer.transform_filepath(pathToCache)
        if not os.path.lexists(stamp):
            os.symlink('#', stamp)

    def _remove_file_stamp(self, filepath):
        pathToCache = self._cache_path(filepath)
        stamp = self._pathTransformer.transform_filepath(pathToCache)
        if not os.path.lexists(stamp):
            os.unlink(stamp)
    '''


class DirWalker(object):

    class DummyMemcache(object):
        def cacheAttributes(self, path, st):
            if loclogger.debug: 
                DEBUG("DummyMemcache.cacheAttributes(%s, %s)" % (path, st))

    def __init__(self, rootpath, relpath = '', memoryCache = DummyMemcache()):
        '''For given directory path get: subdirs, files, links in the dir'''
        self.memoryCache = memoryCache
        self.rootpath = rootpath
        self.relpath = relpath

    def walk(self):
        dirs, files, links = [], [], []
        dirpath = '/'.join([self.rootpath, self.relpath])
        for entry in os.listdir(dirpath):
            if loclogger.debug:
                DEBUG(entry)
            try:
                full_path = os.sep.join([dirpath, entry])
                st = os.lstat(full_path)
                st_mode = st.st_mode
                if stat.S_ISREG(st_mode):
                    files.append(entry)
                elif stat.S_ISDIR(st_mode):
                    dirs.append(entry)
                elif stat.S_ISLNK(st_mode):
                    links.append(entry)
                else:
                    ERROR("unsupported type of file %s" % full_path)

                # TODO: check if we don't need to slightly modify 
                # st struct (because of some i-node info)
                self.memoryCache.cacheAttributes(os.sep.join([self.relpath, entry]), st)

            except OSError:
                ERROR("cannot stat: %s" % full_path)
        return dirs, files, links

    def initialize(self):
        self.dirs, self.files, self.links = self.walk()


class CachedDirWalker(object):

    INITIALIZATION_STAMP = '.cache_initialized'

    def __init__(self, path):
        self._dirs, self._files, self._links = DirWalker(path).walk()
        self.path_transformer = path_factory.PathTransformer()

    @property
    def files(self):
        stamp = CachedDirWalker.INITIALIZATION_STAMP
        if self._links.count(stamp):
            self._links.remove(stamp)
        all_files = self._files + list(set(self._links) - set(self.links))
        return list(set(([
            self.path_transformer.reverseTransformFilepath(filename) 
            for filename in all_files])))

    @property
    def dirs(self):
        stamp = CachedDirWalker.INITIALIZATION_STAMP
        if self._dirs.count(stamp):
            self._dirs.remove(stamp)
        return list(set(([
            self.path_transformer.reverseTransformDirpath(dirname) 
            for dirname in self._dirs
            ])))

    @property
    def links(self):
        return filter(lambda link: not link.endswith(path_factory.PathTransformer.FILE_SUFFIX),
                      self._links)
