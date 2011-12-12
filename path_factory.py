import os 

class PathTransformer(object):

    FILE_SUFFIX = 'filecache'
    DIR_SUFFIX = 'dircache'

    def transformFilepath(self, filepath):
        return '.'.join([filepath, PathTransformer.FILE_SUFFIX])

    def reverseTransformFilepath(self, filepath):
        if filepath.endswith(PathTransformer.FILE_SUFFIX):
            return filepath[:-(len(PathTransformer.FILE_SUFFIX) + 1)]
        return filepath

    def transformDirpath(self, dirpath):
        return '.'.join([dirpath, PathTransformer.DIR_SUFFIX])

    def reverseTransformDirpath(self, dirpath):
        if dirpath.endswith(PathTransformer.DIR_SUFFIX):
            return dirpath[:-(len(PathTransformer.DIR_SUFFIX) + 1)]
        return dirpath

class PathFactory(object):

    def __init__(self, config):
        self._config = config
        self._path_transformer = PathTransformer()

    def createAbsoluteSourcePath(self, path):
        if path == '.':
            return self._config.source_dir
        return "".join([self._config.source_dir, path])

    def createPathToDiskCache(self, path):
        return self._createPathToDiskCache(path)

    def createPathToDiskCacheFileMarker(self, path):
        pathToCache = self._createPathToDiskCache(path)
        return self._path_transformer.transformFilepath(pathToCache)

    def createPathToDiskCacheDirectoryMarker(self, path):
        pathToCache = self._createPathToDiskCache(path)
        return self._path_transformer.transformDirpath(pathToCache)

    def createPathInitializationMarker(self, path, initStamp):
        pathToCache = self._createPathToDiskCache(path)
        return os.sep.join([pathToCache, initStamp])

    def _createPathToDiskCache(self, path):
        root = self._config.cache_root_dir
        if path == '/':
            return root
        return "".join([root, path])

