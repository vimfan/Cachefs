import config
import os
import time

def getConfig():
    test_config                      = config.getConfig()
    test_config.ut_tests_root        = '/home/seba/job/nsn/ssh_cache_fs/test'
    common_prefix                    = os.sep.join([test_config.ut_tests_root, 'current'])
    test_config.ut_current_tc        = common_prefix

    # cache manager specific config options
    cache_prefix                             = common_prefix
    test_config.cache_manager.cache_root_dir = os.sep.join([cache_prefix, 'cache'])
    test_config.cache_manager.source_dir     = os.sep.join([common_prefix, 'cache_fs_source'])

    test_config.cache_fs.cache_fs_mountpoint = os.sep.join([common_prefix, 'cache_fs_mountpoint'])

    return test_config

