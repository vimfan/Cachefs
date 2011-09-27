import config
import os
import time

def getConfig():

    test_config                      = config.getConfig()

    test_config.ut_tests_root        = os.sep.join([config.getCommonPrefix(), 'test_logs'])
    test_config.ut_current_tc        = os.sep.join([test_config.ut_tests_root, 'current'])

    test_config.cache_manager.cache_root_dir = os.sep.join([test_config.ut_current_tc, 'cache'])
    test_config.cache_manager.source_dir     = os.sep.join([test_config.ut_current_tc, 'cache_fs_source'])

    test_config.cache_fs.cache_fs_mountpoint = os.sep.join([test_config.ut_current_tc, 'cache_fs_mountpoint'])

    return test_config

