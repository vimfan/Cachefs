import shutil
import os
import subprocess
import time
import tempfile
import stat
import errno
import logging

import unittest
import mox

import fuse
import config
import test_config
import cachefs
import runner

def logger_tm(f):
    def wrapper(*args, **kw):
        class_name = args[0].__class__.__name__
        func_name = f.func_name
        logging.debug("TESTCASE ---------- %s.%s ---------------" % (class_name, func_name))
        retval =  f(*args, **kw)
        logging.debug("END OF TESTCASE ---------- %s.%s ---------------" % (class_name, func_name))
        return retval
    wrapper.func_name = f.func_name
    wrapper.__doc__ = f.__doc__
    return wrapper

class TestHelper:

    @staticmethod
    def get_cfg_for_test():
        return test_config.getConfig()

    @staticmethod
    def create_source_dir(cfg, path = ''):
        if path:
            source_dir = os.sep.join([cfg.source_dir, path])
        else:
            source_dir = cfg.source_dir
        os.makedirs(source_dir)

    @staticmethod
    def remove_source_dir(cfg, path = ''):
        assert(cfg.source_dir)
        if path:
            source_dir = os.sep.join([cfg.source_dir, path])
        else:
            source_dir = cfg.source_dir
        shutil.rmtree(source_dir)

    @staticmethod
    def remove_source_file(cfg, subpath):
        source_path = os.sep.join([cfg.source_dir, subpath])
        os.unlink(source_path)

    @staticmethod
    def create_source_file(cfg, subpath, content = ''):
        source_path = os.sep.join([cfg.source_dir, subpath])
        f = open(source_path, 'w')
        f.write(content)
        f.close()

    @staticmethod
    def create_remote_dir(cfg, path = ''):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        if path:
            remote_dir = os.sep.join([cfg.remote_dir, path])
        else:
            remote_dir = cfg.remote_dir
        standalone_cmd = " ".join(['mkdir', '-p', remote_dir])
        user_host = "@".join([cfg.user, cfg.server])
        call_args = [cfg.ut_ssh_bin, user_host, standalone_cmd]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def remove_remote_dir(cfg, path = ''):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        if path:
            remote_dir = os.sep.join([cfg.remote_dir, path])
        else:
            remote_dir = cfg.remote_dir
        standalone_cmd = " ".join(['rm', '-rf', remote_dir])
        user_host = "@".join([cfg.user, cfg.server])
        call_args = [cfg.ut_ssh_bin, user_host, standalone_cmd]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def remove_remote_file(cfg, subpath):
        assert(isinstance(cfg, config.Config.SshfsManagerConfig))
        remote_file = os.sep.join([cfg.remote_dir, subpath])
        standalone_cmd = " ".join(['rm', '-rf', remote_file])
        user_host = "@".join([cfg.user, cfg.server])
        call_args = [cfg.ut_ssh_bin, user_host, standalone_cmd]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def create_remote_file(cfg, rel_path, content = ''):
        named_tmp_file = tempfile.NamedTemporaryFile()
        named_tmp_file.write(content)
        named_tmp_file.flush()
        user_host = "@".join([cfg.user, cfg.server])
        path = os.sep.join([cfg.remote_dir, rel_path])
        user_host_path = ":".join([user_host, path])
        call_args = [cfg.ut_scp_bin, named_tmp_file.name, user_host_path]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))
        named_tmp_file.close() # automatically will be removed

    @staticmethod
    def execute_remote(cfg, script):
        rel_path = 'remote_cmd.sh'
        named_tmp_file = tempfile.NamedTemporaryFile('wx+b')
        named_tmp_file.write(script)
        named_tmp_file.flush()
        os.chmod(named_tmp_file.name, 0777)
        user_host = "@".join([cfg.user, cfg.server])
        script_path = os.sep.join([cfg.remote_dir, rel_path])
        user_host_path = ":".join([user_host, script_path])
        call_args = [cfg.ut_scp_bin, named_tmp_file.name, user_host_path]
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))
        named_tmp_file.close() # automatically will be removed
        # execute:
        call_args = [cfg.ut_ssh_bin, user_host, "cd %s; %s" % (cfg.remote_dir, script_path)]
        print subprocess.Popen(call_args, shell = False, stdout = subprocess.PIPE).communicate()[0]
        call_args = [cfg.ut_ssh_bin, user_host, "cd %s; rm %s" % (cfg.remote_dir, script_path)]
        assert(0 == subprocess.call(call_args, shell = False, stdout = fnull))

    @staticmethod
    def execute_source(cfg, script):
        cwd = os.getcwd()
        os.chdir(cfg.cache_manager.source_dir)
        named_tmp_file = tempfile.NamedTemporaryFile('wx+b')
        named_tmp_file.write(script)
        named_tmp_file.flush()
        TMP_BIN = '/tmp/tmp_bin'
        shutil.copyfile(named_tmp_file.name, TMP_BIN)
        os.chmod(TMP_BIN, 0777)
        fnull = open(os.devnull, 'w')
        assert(0 == subprocess.call([TMP_BIN], shell = True, stdout = fnull))
        os.unlink(TMP_BIN)
        os.chdir(cwd)


class ModuleTestCase(unittest.TestCase):

    def setUp(self):
        cfg = TestHelper.get_cfg_for_test()
        tests_root = cfg.ut_tests_root
        testcase_current = cfg.ut_current_tc
        tc_wdir = self.__test_dir = os.sep.join([tests_root, self.__class__.__name__])
        if os.path.exists(tc_wdir):
            shutil.rmtree(tc_wdir)
        os.makedirs(tc_wdir)
        if os.path.lexists(testcase_current):
            os.remove(testcase_current)
        os.symlink(tc_wdir, testcase_current)

        return self.setUpImpl()

    def tearDown(self):
        self.tearDownImpl()
        shutil.rmtree(self.__test_dir)
        cfg = TestHelper.get_cfg_for_test()
        os.remove(cfg.ut_current_tc)

class CacheFsUnitTest(unittest.TestCase):

    def setUp(self):
        self.sut = cachefs.CacheFs(TestHelper.get_cfg_for_test())

    def tearDown(self):
        pass

    @logger_tm
    def test_access(self):
        # inject mock
        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)

        # setup mock
        cache_mgr_mock.exists('file1').AndReturn(True)
        cache_mgr_mock.exists('file2').AndReturn(False)
        cache_mgr_mock.exists('file3').AndReturn(True)
        mox.Replay(cache_mgr_mock)

        failure = -errno.EACCES
        success = 0
        self.assertEqual(success, self.sut.access('file1', os.F_OK));
        self.assertEqual(failure, self.sut.access('file2', os.F_OK));
        self.assertEqual(success, self.sut.access('file3', os.F_OK));
        self.assertEqual(failure, self.sut.access('file3', os.W_OK));
        self.assertEqual(success, self.sut.access('file4', os.R_OK | os.X_OK));

    @logger_tm
    def test_readdir(self):
        DIRPATH = '/DIR'
        dir_entries = ['file', 'subdir', 'file2']

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(True)
        cache_mgr_mock.list_dir(DIRPATH).AndReturn(dir_entries)
        mox.Replay(cache_mgr_mock)

        dir_entries_match = dir_entries + ['.', '..']
        readdir_entries = []

        for entry in self.sut.readdir(DIRPATH, 0, ''):
            self.assertTrue(isinstance(entry, fuse.Direntry))
            self.assertTrue(entry.name in dir_entries_match)
            readdir_entries.append(entry.name)

        self.assertEqual(sorted(dir_entries_match), sorted(readdir_entries))

    @logger_tm
    def test_readdir_dir_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    @logger_tm
    def test_readdir_on_file(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.readdir(DIRPATH).next())

    @logger_tm
    def test_opendir_success(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(True)
        cache_mgr_mock.is_dir(DIRPATH).AndReturn(True)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(None, self.sut.opendir(DIRPATH))

    @logger_tm
    def test_opendir_not_dir(self):
        FILEPATH = '/FILE'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(FILEPATH).AndReturn(True)
        cache_mgr_mock.is_dir(FILEPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(FILEPATH))

    @logger_tm
    def test_opendir_path_not_exists(self):
        DIRPATH = '/DIR'

        cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        cache_mgr_mock.exists(DIRPATH).AndReturn(False)
        mox.Replay(cache_mgr_mock)

        self.assertEqual(-errno.ENOENT, self.sut.opendir(DIRPATH))

    #@logger_tm
    #def test_readlink_success(self):
        #FILEPATH = '/File'
        #CACHED_FILE_PATH = "/ABSOLUTE/PATH/TO/CACHED/FILE"

        #cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        #cache_mgr_mock.get_path_to_file(FILEPATH).AndReturn(CACHED_FILE_PATH)
        #mox.Replay(cache_mgr_mock)

        #self.assertEqual(CACHED_FILE_PATH, self.sut.readlink(FILEPATH))

    #@logger_tm
    #def test_readlink_not_found(self):
        #FILEPATH = '/File'

        #cache_mgr_mock = self.sut.cache_mgr = mox.MockObject(cachefs.CacheManager)
        #cache_mgr_mock.get_path_to_file(FILEPATH).AndReturn(None)
        #mox.Replay(cache_mgr_mock)

        #self.assertEqual(-errno.ENOENT, self.sut.readlink(FILEPATH))

class CacheFsModuleTest(ModuleTestCase):

    def precondition(self):
        pass

    def setUpImpl(self):
        cfg = self.cfg = TestHelper.get_cfg_for_test()
        mountpoint = cfg.cache_fs.cache_fs_mountpoint
        self.assertTrue(not os.path.ismount(mountpoint), msg=mountpoint)
        if not os.path.exists(mountpoint):
            os.makedirs(mountpoint)
        TestHelper.create_source_dir(cfg.cache_manager)
        self.precondition()
        self.runner = runner.CacheFsRunner(test_config)
        self.runner.run()

    def tearDownImpl(self):
        self.runner.stop()
        TestHelper.remove_source_dir(self.cfg.cache_manager)
        # add some safety checks
        assert(self.cfg.cache_manager.cache_root_dir)
        shutil.rmtree(self.cfg.cache_manager.cache_root_dir)

class TestDirectoriesOnly(CacheFsModuleTest):

    SUBDIR_1 = 'subdir1'
    SUBDIR_2 = 'subdir2'
    SUB_SUBDIR_2 = 'subdir2.1'

    def precondition(self):
        cfg = self.cfg.cache_manager
        TestHelper.create_source_dir(cfg, TestDirectoriesOnly.SUBDIR_1)
        TestHelper.create_source_dir(cfg, TestDirectoriesOnly.SUBDIR_2)
        TestHelper.create_source_dir(cfg,
                                     os.sep.join([TestDirectoriesOnly.SUBDIR_2,
                                                  TestDirectoriesOnly.SUB_SUBDIR_2]))

    @logger_tm
    def test(self):
        '''Module test: Check directories'''
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        path, dirs, files = os.walk(mountpoint).next()
        self.assertTrue(TestDirectoriesOnly.SUBDIR_1 in dirs)
        self.assertTrue(TestDirectoriesOnly.SUBDIR_2 in dirs)
        self.assertEqual(2, len(dirs))
        self.assertEqual(0, len(files))

        cache_root = self.cfg.cache_manager.cache_root_dir

        subdir2_path = os.sep.join([mountpoint, TestDirectoriesOnly.SUBDIR_2])
        path, dirs, files = os.walk(subdir2_path).next()
        self.assertEqual(1, len(dirs))
        self.assertEqual(0, len(files))
        self.assertEqual(sorted([TestDirectoriesOnly.SUB_SUBDIR_2]), sorted(dirs))

        sub_subdir2_path = os.sep.join([mountpoint,
                                        TestDirectoriesOnly.SUBDIR_2,
                                        TestDirectoriesOnly.SUB_SUBDIR_2])
        path, dirs, files = os.walk(sub_subdir2_path).next()
        self.assertEqual(0, len(dirs))
        self.assertEqual(0, len(files))

class TestDirectoriesAndFiles(CacheFsModuleTest):

    SUBDIR_1 = 'subdir1'
    FILE_1 = 'file1'
    FILE_1_CONTENT = 'file1 content'

    FILE_2 = 'file2'
    FILE_2_SUBPATH = os.sep.join([SUBDIR_1, FILE_2])
    FILE_2_CONTENT = 'file2 content'

    def precondition(self):
        #sshcfg = self.cfg.ssh
        cls = TestDirectoriesAndFiles
        cfg = self.cfg.cache_manager
        TestHelper.create_source_file(cfg, cls.FILE_1, cls.FILE_1_CONTENT)
        TestHelper.create_source_dir(cfg, cls.SUBDIR_1)
        TestHelper.create_source_file(cfg, cls.FILE_2_SUBPATH, cls.FILE_2_CONTENT)

    @logger_tm
    def test(self):
        '''Module test: Check directories and files'''
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        path, dirs, files = os.walk(mountpoint).next()

        cls = TestDirectoriesAndFiles

        self.assertEqual(1, len(dirs))
        self.assertEqual(cls.SUBDIR_1, dirs[0])

        self.assertEqual(1, len(files))
        self.assertEqual(cls.FILE_1, files[0])

        file1_path = os.sep.join([mountpoint, files[0]])
        self.assertEqual(cls.FILE_1_CONTENT, open(file1_path).read())

        dir_path = os.sep.join([mountpoint, dirs[0]])

        def check_file():
            path, dirs, files = os.walk(dir_path).next()
            self.assertEqual(1, len(files))
            self.assertEqual(cls.FILE_2, files[0])
            file2_path = os.sep.join([mountpoint, cls.SUBDIR_1, cls.FILE_2])
            os.path.islink(file2_path)
            self.assertEqual(cls.FILE_2_CONTENT, open(file2_path).read())

        check_file()
        TestHelper.remove_source_file(self.cfg.cache_manager, cls.FILE_2_SUBPATH)
        check_file() # after removing file remote it shall remain in cache
                     # contextual way of checking if cache is really working

class RelativePaths(CacheFsModuleTest):

    SUBDIR = 'subdir'
    FILE = 'file'
    FILE_CONTENT = 'content'

    SUBDIR_2 = 'subdir/subdir2'
    FILE_2 = 'subdir/subdir2/file2'
    FILE_CONTENT_2 = 'content2'

    SUBDIR_3 = 'subdir/subdir2/subdir3'
    FILE_3 = 'subdir/subdir2/subdir3/file3'
    FILE_CONTENT_3 = 'content3'

    def precondition(self):
        cfg = self.cfg.cache_manager
        cls = RelativePaths
        TestHelper.create_source_dir(cfg, cls.SUBDIR)
        TestHelper.create_source_file(cfg, cls.FILE, cls.FILE_CONTENT)

        TestHelper.create_source_dir(cfg, cls.SUBDIR_2)
        TestHelper.create_source_file(cfg, cls.FILE_2, cls.FILE_CONTENT_2)

        TestHelper.create_source_dir(cfg, cls.SUBDIR_3)
        TestHelper.create_source_file(cfg, cls.FILE_3, cls.FILE_CONTENT_3)

    @logger_tm
    def test(self):
        '''Module test: Relative paths'''

        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint
        cls = RelativePaths

        normalized_filepath = os.sep.join([mountpoint, 'file'])
        self.assertTrue(os.path.lexists(normalized_filepath))
        self.assertEqual(cls.FILE_CONTENT, open(normalized_filepath).read())

        FILE_RELATIVE = 'subdir/subdir2/subdir3/../../../file'
        rel_filepath = os.sep.join([mountpoint, FILE_RELATIVE])
        self.assertTrue(os.path.lexists(rel_filepath))
        self.assertEqual(cls.FILE_CONTENT, open(rel_filepath).read())

        FILE2_RELATIVE = 'subdir/./subdir2/subdir3/../file2'
        rel_filepath2 = os.sep.join([mountpoint, FILE2_RELATIVE])
        self.assertTrue(os.path.lexists(rel_filepath2))
        self.assertEqual(cls.FILE_CONTENT_2, open(rel_filepath2).read())

class SymbolicLinks(CacheFsModuleTest):

    def precondition(self):
        TestHelper.execute_source(self.cfg, '''
            mkdir -p a/b/c

            mkdir -p e/f/g
            touch e/f/g/1.txt

            mkdir -p i/f/g
            touch i/f/g/2.txt

            ln -s ../../../i/f/g e/f/g/j''')

    @logger_tm
    def test(self):
        '''Module test: Symbolic links'''
        mountpoint = self.cfg.cache_fs.cache_fs_mountpoint

        full_path = os.sep.join([mountpoint, 'a/b/c'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isdir(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isdir(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/1.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))

        full_path = os.sep.join([mountpoint, 'i/f/g/2.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))
        full_path = os.sep.join([mountpoint, 'e/f/g/j'])

        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.islink(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j/2.txt'])
        self.assertTrue(os.path.exists(full_path))
        self.assertTrue(os.path.isfile(full_path))
        self.assertTrue(os.path.islink(full_path))

        full_path = os.sep.join([mountpoint, 'e/f/g/j/1.txt'])
        self.assertFalse(os.path.exists(full_path))


class CacheManagerModuleTest(ModuleTestCase):

    def setUpImpl(self):
        self.cfg = TestHelper.get_cfg_for_test()
        self.sut = cachefs.CacheManager(self.cfg.cache_manager)
        TestHelper.create_source_dir(self.cfg.cache_manager)
        self.sut.run()

    def tearDownImpl(self):
        self.sut.stop()
        TestHelper.remove_source_dir(self.cfg.cache_manager)
        shutil.rmtree(self.sut.cfg.cache_root_dir)


class CreateCacheDir(CacheManagerModuleTest):

    @logger_tm
    def test_create_cache_dir(self):
        self.assertTrue(os.path.exists(self.sut.cfg.cache_root_dir))

class Exists(CacheManagerModuleTest):

    @logger_tm
    def test_exists(self):
        file_path = '/TestCacheManager.test_exists.txt'
        TestHelper.create_source_file(self.cfg.cache_manager,
                                      file_path,
                                      '.' * 5)
        self.assertTrue(self.sut.exists(file_path))

class ExistsRoot(CacheManagerModuleTest):

    @logger_tm
    def test_exists_root(self):
        file_path = '/'
        self.assertTrue(self.sut.exists(file_path))

class IsDir(CacheManagerModuleTest):

    @logger_tm
    def test_is_dir(self):
        dir_path = '/TestCacheManager.test_is_dir'
        TestHelper.create_source_dir(self.cfg.cache_manager, dir_path)
        self.assertTrue(self.sut.exists(dir_path))
        self.assertTrue(self.sut.is_dir(dir_path))

class ListDir(CacheManagerModuleTest):
    @logger_tm
    def test_list_dir(self):
        dir_path = "/TestCacheManager.test_list_dir"
        cfg = self.cfg.cache_manager
        TestHelper.create_source_dir(cfg, dir_path)

        subdir_name = 'subdir'
        dir_path2 = os.sep.join([dir_path, subdir_name])
        TestHelper.create_source_dir(cfg, dir_path2)

        file_name = '1.txt'
        file_path = os.sep.join([dir_path, file_name])
        TestHelper.create_source_file(cfg, file_path, 'file_content ... ')

        self.assertTrue(self.sut.exists(dir_path))
        #precond: 
        self.sut.get_attributes(dir_path)

        list_dir_out = self.sut.list_dir(dir_path)
        self.assertTrue(self.sut._has_init_stamp(dir_path))

        input = [file_name, subdir_name]
        self.assertEqual(sorted(input), sorted(list_dir_out))

        cache_root_path = self.sut.cfg.cache_root_dir 
        cache_dir_walker = cachefs.CacheManager.CachedDirWalker(cache_root_path)
        path_transformer = cachefs.CacheManager.PathTransformer()

        cached_subdir_path = os.sep.join(
            [cache_root_path, dir_path, path_transformer.transform_dirpath(subdir_name)])

        self.assertTrue(os.path.exists(cached_subdir_path))

        cached_file_path = os.sep.join(
            [cache_root_path, path_transformer.transform_filepath(file_name)])

        self.assertFalse(os.path.exists(cached_file_path))

class Getattr(CacheManagerModuleTest):
    @logger_tm
    def test(self):
        self.sut.get_attributes('.')

