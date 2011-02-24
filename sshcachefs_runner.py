#!/usr/bin/env python

import sys
import subprocess
import os
import time

class SshCacheFsRunner(object):

    def __init__(self, cfg_module):
        self.cfg_module = cfg_module
        exec('import %s as config' % self.cfg_module)
        self.cfg = config.getConfig()
        self._process_handle = None

    def run(self):
        assert(self.cfg.cacheFs.cache_fs_mountpoint)
        assert(self.cfg_module)
        self._process_handle = subprocess.Popen(['python',
                                                 'sshcachefs.py',
                                                 self.cfg.cacheFs.cache_fs_mountpoint,
                                                 self.cfg_module])
        self._wait_for_mount()

    def stop(self):
        mountpoint = self.cfg.cacheFs.cache_fs_mountpoint
        if (os.path.ismount(mountpoint)):
            subprocess.call([self.cfg.ssh.fusermount_bin, '-u', mountpoint])
        else:
            pid = self._process_handle.pid
            os.kill(pid, signal.SIGINT)

    def _wait_for_mount(self):
        assert(self._process_handle)
        assert(self.cfg)

        mountpoint = self.cfg.cacheFs.cache_fs_mountpoint
        assert(mountpoint)

        def is_mount():
            return os.path.ismount(mountpoint)

        interval = 0.2
        wait_for_mount = 30
        time_start = time.time()
        time_elapsed = 0
        mounted = is_mount()
        while ((not mounted) and time_elapsed < wait_for_mount):
            time.sleep(interval)
            mounted = is_mount()
            time_elapsed = time.time() - time_start
        if not mounted:
            raise Exception("Filesystem not mounted after %d secs" % wait_for_mount)

def main():
    assert(len(sys.argv) == 2)
    runner = SshCacheFsRunner(sys.argv[1])
    runner.run()

if __name__ == '__main__':
    main()
