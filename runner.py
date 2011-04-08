#!/usr/bin/env python

import sys
import subprocess
import os
import time
import logging

class SshCacheFsRunner(object):

    def __init__(self, cfg_module):
        self.cfg_module = cfg_module
        self.cfg = cfg_module.getConfig()
        self._process_handle = None

    def run(self):
        assert(self.cfg.cache_fs.cache_fs_mountpoint)
        assert(self.cfg_module)

        self._process_handle = subprocess.Popen(['coverage',
                                                 'run',
                                                 'sshcachefs.py',
                                                 self.cfg.cache_fs.cache_fs_mountpoint,
                                                 self.cfg_module.__name__, 
                                                 '-f'])
        '''
        self._process_handle = subprocess.Popen(['python',
                                                 'sshcachefs.py',
                                                 self.cfg.cache_fs.cache_fs_mountpoint,
                                                 self.cfg_module.__name__, 
                                                 '-f'])
                                                 '''
        self._wait_for_mount()

    def stop(self):
        logging.info("Stopping SshCacheFs")
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        if (os.path.ismount(mountpoint)):
            logging.info("Calling: fusermount -u %s" % mountpoint)
            subprocess.call([self.cfg.ssh.fusermount_bin, '-u', mountpoint])
        else:
            pid = self._process_handle.pid
            logging.info("Killing SshCacheFs")
            os.kill(pid, signal.SIGINT)

    def _wait_for_mount(self):
        assert(self._process_handle)
        assert(self.cfg)

        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        assert(mountpoint)

        def is_mount():
            return os.path.ismount(mountpoint)

        interval = 0.2
        wait_for_mount = 3
        logging.info("Waiting for mount: %s sec" % wait_for_mount)
        time_start = time.time()
        time_elapsed = 0
        mounted = is_mount()
        while ((not mounted) and time_elapsed < wait_for_mount):
            time.sleep(interval)
            mounted = is_mount()
            time_elapsed = time.time() - time_start
        if not mounted:
            raise Exception("Filesystem not mounted after %d secs" % wait_for_mount)

        logging.info("Filesystem mounted after %s seconds" % time_elapsed)

def main():
    assert(len(sys.argv) == 2)
    exec('import %s as config' % sys.argv[1])
    runner = SshCacheFsRunner(config)
    runner.run()

if __name__ == '__main__':
    main()
