import unittest
import memfs_log

class CreateAndDrop(unittest.TestCase):

    def test_createAndDrop(self):
        memfs_log.create_database('db.sqlite3')
        memfs_log.drop_database()

class Insert(unittest.TestCase):

    def setUp(self):
        memfs_log.create_database('db.sqlite3')

    def tearDown(self):
        memfs_log.drop_database()

    def test(self):
        params = ['one', 1, {}]
        output = ['output', 'shit', 2]
        operation = 'getattr'
        memfs_log.insert(operation, params, output)
        logs = memfs_log.select()
        self.assertEqual(len(logs), 1)

        log_item = logs[0]
        self.assertEqual(operation, log_item[memfs_log.MemfsLog.NAME])
        self.assertEqual(params, log_item[memfs_log.MemfsLog.PARAMS])
        self.assertEqual(output, log_item[memfs_log.MemfsLog.OUTPUT])
