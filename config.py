'''
    class SshfsManagerConfig(object):
        def __init__(self):
            self.sshfs_bin        = '/usr/bin/sshfs'
            self.sshfs_options    = ['-f', '-o', 'transform_symlinks']
            self.fusermount_bin   = '/usr/bin/fusermount'
            self.sshfs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/.sshfs_mount'
            self.server           = 'localhost'
            self.user             = 'seba'
            self.remote_dir       = '/studinfo/sebam'
            self.wait_for_mount   = 30
'''


class Config(object):

    class CacheManagerConfig(object):

        def __init__(self):
            self.cache_root_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'
            # FIXME: move to cache fs cfg
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
