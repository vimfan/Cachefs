import sqlite3
import pickle

__conn = None
__TABLE_NAME = 'memfs_log'

class MemfsLog(object):
    ID = 'id'
    NAME = 'name'
    PARAMS = 'params'
    OUTPUT = 'output'
    TIME = 'time'

    @staticmethod
    def columns():
        return [MemfsLog.ID, MemfsLog.NAME, MemfsLog.PARAMS, MemfsLog.OUTPUT, MemfsLog.TIME]

def create_database(filepath):
    global __conn
    __conn = sqlite3.connect(filepath)
    c = __conn.cursor()
    c.execute('''
            create table IF NOT EXISTS {tablename} ( 
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {name} TEXT, 
                {params} BLOB, 
                {output} BLOB, 
                {time} TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
                )'''.format(
                tablename=__TABLE_NAME,
                name = MemfsLog.NAME,
                params = MemfsLog.PARAMS,
                output = MemfsLog.OUTPUT,
                time = MemfsLog.TIME))
    __conn.commit()
    c.close()

def drop_database():
    global __conn
    assert(__conn)
    c = __conn.cursor()
    c.execute("drop table {tablename}".format(tablename=__TABLE_NAME))
    __conn.commit()
    c.close()

def insert(operation, params = None, output = None):
    global __conn
    assert(__conn)
    c = __conn.cursor()
    def dumpPickleIfPossible(obj):
        try:
            objPickle = pickle.dumps(obj)
            return objPickle
        except TypeError, inst:
            return pickle.dumps(str(obj))
            
    to_insert = {
        MemfsLog.NAME   : operation,
        MemfsLog.PARAMS : dumpPickleIfPossible(params),
        MemfsLog.OUTPUT : dumpPickleIfPossible(output)
    }
    sorted_keys = list(sorted(to_insert.keys()))
    placeholders = ','.join(['?' for i in range(len(to_insert))]) # ?, ?, ?, ?
    values = tuple([to_insert[key] for key in sorted_keys])
    stmt = "INSERT INTO {tablename} ({columns}) VALUES ({placeholders})".format(
                tablename = __TABLE_NAME, columns=','.join(sorted_keys), placeholders=placeholders)
    c.execute(stmt, values)

    __conn.commit()
    c.close()

def select():
    global __conn
    assert(__conn)
    c = __conn.cursor()
    result_columns = ','.join(MemfsLog.columns())
    select = '''select {columns} from {tablename}'''.format(columns = result_columns, tablename=__TABLE_NAME)
    ret = []
    c.execute(select)

    def getField(row, field):
        value = row[MemfsLog.columns().index(field)]
        to_unpickle = [MemfsLog.PARAMS, MemfsLog.OUTPUT]
        if field in to_unpickle:
            # sqlite3 returns unicode, and pickle expects str
            # hopefully we won't have problems with this
            value = pickle.loads(str(value))
        return value

    for row in c:
        ret.append(
            dict(zip(MemfsLog.columns(), map(lambda field: getField(row, field), MemfsLog.columns())))
        )
    return ret
