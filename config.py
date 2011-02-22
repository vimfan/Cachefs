
class Config(object):

    class SshfsManagerConfig(object):
        def __init__(self):
            self.sshfs_bin        = '/usr/bin/sshfs'
            self.sshfs_options    = ['-f', '-o', 'follow_symlinks']
            self.fusermount_bin   = '/usr/bin/fusermount'
            self.sshfs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/.sshfs_mount'
            self.server           = 'localhost'
            self.user             = 'seba'
            self.remote_dir       = '/studinfo/sebam'
            self.wait_for_mount   = 30

    class CacheManagerConfig(object):

        def __init__(self):
            self.cache_root_dir = '/home/seba/job/nsn/ssh_cache_fs/.cache'

    class CacheFsConfig(object):

        def __init__(self):
            self.cache_fs_mountpoint = '/home/seba/job/nsn/ssh_cache_fs/cachefs'

    def __init__(self):
        self.ssh = Config.SshfsManagerConfig()
        self.cache = Config.CacheManagerConfig()
        self.cacheFsConfig = Config.CacheFsConfig()

def getConfig():
    return Config()
