#!/usr/bin/env python

import sys
import subprocess
import time
import config
import os
import logging
import signal

class FuseFsMounter(object):

    def __init__(self, cmdline):
        self._mountpoint = cmdline[1]
        self._cmdline = cmdline
        print(self._mountpoint)
        assert(os.path.isdir(self._mountpoint))

        self._processHandle = None
        self._cfg = config.getConfig()

    def mount(self):
        print(self._cmdline)
        self._processHandle = subprocess.Popen(self._cmdline)
        self._wait_for_mount()

    def unmount(self):
        mountpoint = self._mountpoint

        if not os.path.ismount(mountpoint):
            pid = self._processHandle.pid
            logging.info("killing filesystem process")
            os.kill(pid, signal.SIGINT)
            return

        curr_attempt = 0
        interval = 0.01
        num_of_attemps = 10 / interval
        devnull = open(os.devnull) # to disable warnings
        while os.path.ismount(mountpoint) and curr_attempt < num_of_attemps:
            logging.info("Calling fusermount -u")
            try:
                subprocess.check_call([self._cfg.cache_fs.fusermount_bin, '-u', mountpoint], stderr=devnull)
            except subprocess.CalledProcessError, e:
                time.sleep(0.1)
                curr_attempt += 1
        if curr_attempt == num_of_attemps:
            print("Didn't manage to unmount filesystem after 10s, and {num_attempts}".format(num_attempts=curr_attempt))


    def _wait_for_mount(self):

        def is_mount():
            return os.path.ismount(self._mountpoint)

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
    mounter = FuseFsMounter(sys.argv[1:])
    mounter.mount()
    time.sleep(2)
    mounter.unmount()

if __name__ == '__main__':
    main()
