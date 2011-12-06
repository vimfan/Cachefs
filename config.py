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
            self.disk_cache_lifetime = 600
            self.memory_cache_lifetime = 60

    class CacheFsConfig(object):

        def __init__(self):
            self.cache_fs_mountpoint = os.path.join(getCommonPrefix(), 'cachefs')
            self.fusermount_bin   =    '/bin/fusermount'

    def __init__(self):
        self.cache_manager = Config.CacheManagerConfig()
        self.cache_fs = Config.CacheFsConfig()

class ConfigValidator(object):

    class ConfigError(BaseException):
        def __init__(self, msg):
            self.msg = msg

    class ConfigWarning(BaseException):
        pass

    def __init__(self):
        pass

    def validate(self, cfg):

        mountpoint = cfg.cache_fs.cache_fs_mountpoint
        source_dir = cfg.cache_manager.source_dir
        cache_dir  = cfg.cache_manager.cache_root_dir

        if not source_dir:
            raise ConfigValidator.ConfigError("Parameter source_dir is mandatory")
        if not os.path.lexists(source_dir):
            raise ConfigValidator.ConfigError("Source dir " + source_dir + " does not exist")

        if not cache_dir:
            raise ConfigValidator.ConfigError("Parameter cache_dir is mandatory")

        if not mountpoint:
            raise ConfigValidator.ConfigError("Mountpoint is mandatory")

        if not os.path.lexists(mountpoint):
            raise ConfigValidator.ConfigError("Mountpoint dir " + mountpoint + " does not exist")

def getConfig():
    return Config()

def get_validator():
    return ConfigValidator()
