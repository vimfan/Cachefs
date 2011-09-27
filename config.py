import os
import sys

def getProjectRoot():
    return os.path.dirname(os.path.abspath('cachefs.py'))

def getCommonPrefix():
    return os.getcwd()

class Config(object):

    class CacheManagerConfig(object):

        def __init__(self):
            self.cache_root_dir = os.path.join(getCommonPrefix(), '.cache')
            self.source_dir = os.path.join(getCommonPrefix(), 'sshfs')
            self.long_stamp = None
            self.short_stamp = None

    class CacheFsConfig(object):

        def __init__(self):
            self.cache_fs_mountpoint = os.path.join(getCommonPrefix(), 'cachefs')
            self.fusermount_bin   =    '/bin/fusermount'

    def __init__(self):
        self.cache_manager = Config.CacheManagerConfig()
        self.cache_fs = Config.CacheFsConfig()

class Validator(object):

    class ConfigError(object):
        pass

    class ConfigWarning(object):
        pass

    def __init__(self):
        pass

    def validate(self, cfg):
        return True

def getConfig():
    return Config()

def get_validator():
    return Validator()
