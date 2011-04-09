class Config(object):

    class CacheManagerConfig(object):

        def __init__(self):
            self.cache_root_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'
            self.source_dir = '/home/seba/job/nsn/ssh_cache_fs/sshfs'

    class CacheFsConfig(object):

        def __init__(self):
            self.cache_fs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/cachefs'
            self.fusermount_bin   =    '/usr/bin/fusermount'

    def __init__(self):
        self.cache_manager = Config.CacheManagerConfig()
        self.cache_fs = Config.CacheFsConfig()

def getConfig():
    return Config()
