class Config(object):

    class CacheManagerConfig(object):

        def __init__(self):
            self.cache_root_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'
            self.source_dir = '/home/seba/job/nsn/ssh_cache_fs/sshfs'
            self.long_stamp = None
            self.short_stamp = None

    class CacheFsConfig(object):

        def __init__(self):
            self.cache_fs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/cachefs'
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
