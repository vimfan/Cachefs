import config
import os
import time

def getConfig():
    test_config                      = config.getConfig()
    test_config.ut_tests_root        = '/home/seba/job/nsn/ssh_cache_fs/test'
    common_prefix                    = os.sep.join([test_config.ut_tests_root, 'current'])
    test_config.ut_current_tc        = common_prefix

    # sshfs specific configuration options
    sshfs_prefix                     = os.sep.join([common_prefix, 'sshfs'])
    test_config.ut_cleanup_dir       = sshfs_prefix
    test_config.ssh.ut_ssh_bin       = '/usr/bin/ssh'
    test_config.ssh.ut_scp_bin       = '/usr/bin/scp'
    test_config.ssh.server           = 'localhost'
    test_config.ssh.user             = 'seba'
    test_config.ssh.remote_dir       = os.sep.join([sshfs_prefix, 'remote_dir'])
    test_config.ssh.sshfs_mountpoint = os.sep.join([sshfs_prefix, 'sshfs_mountpoint'])
    test_config.ssh.wait_for_mount   = 3.0
    #test_config.ssh.sshfs_options    = ['-f', '-o', 'follow_symlinks']
    test_config.ssh.sshfs_options    = ['-f', '-o', 'transform_symlinks']

    # cache manager specific config options
    cache_prefix                            = common_prefix
    test_config.cache_manager.cache_root_dir = os.sep.join([cache_prefix, 'cache'])

    # cache filesystem options
    #test_config.mountpoint                  = os.sep.join([common_prefix, 'mountpoint'])

    test_config.cache_fs.cache_fs_mountpoint = os.sep.join([common_prefix, 'cache_fs_mountpoint'])

    return test_config

