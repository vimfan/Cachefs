import shutil
import os
import test_config
import tempfile
import subprocess
from mocks.commport import InPort

class TestHelper:

    @staticmethod
    def get_cfg():
        return test_config.getConfig()

    @staticmethod
    def fetch_all(port):
        ret = []
        try:
            while True:
                msg = port.receive(0.2)
                ret.append(msg)
        except InPort.Timeout, e:
            print("All message received from port, number: " + str(len(ret)))
            pass
        return ret


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
            source_dir = os.path.join(cfg.source_dir, path)
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

