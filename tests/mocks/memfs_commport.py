import sqlite3
import pickle
import os
from multiprocessing.connection import Listener

import socket
import threading
import SocketServer
import pickle
# might be rewritten with register_converter, register_adapter functions


__conn = None
__file = None
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

def create(filepath):
    global __file
    assert(not os.path.exists(filepath))
    __file = filepath
    _create_database(filepath)

def register(filepath):
    global __conn
    global __file
    assert(not __conn)
    assert(not __file)
    assert(os.path.exists(filepath))
    __conn = sqlite3.connect(filepath)
    __file = filepath

def destroy():
    global __file
    global __conn
    #assert(os.path.lexists(__file))
    os.remove(__file)
    __file = None
    __conn = None

def deque():
    return _select()

def enqueue(operation, params = None, output = None):
    return _insert(operation, params, output)

'''
# don't need it
def drop_database():
    global __conn
    assert(__conn)
    c = __conn.cursor()
    c.execute("drop table {tablename}".format(tablename=__TABLE_NAME))
    __conn.commit()
    c.close()
'''

def _create_database(filepath):
    global __conn
    __conn = sqlite3.connect(filepath)
    c = __conn.cursor()
    c.execute('''
            create table {tablename} ( 
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {name} TEXT, 
                {params} BLOB, 
                {output} BLOB, 
                {time} TEXT 
                )'''.format(
                tablename=__TABLE_NAME,
                name = MemfsLog.NAME,
                params = MemfsLog.PARAMS,
                output = MemfsLog.OUTPUT,
                time = MemfsLog.TIME))
    __conn.commit()
    c.close()



def _insert(operation, params, output):
    global __conn
    assert(__conn)
    c = __conn.cursor()
    to_insert = {
        MemfsLog.NAME   : operation,
        MemfsLog.PARAMS : `params`, #pickle.dumps(params),
        MemfsLog.OUTPUT : `output`, #pickle.dumps(output),
        MemfsLog.TIME   : "strftime('%Y-%m-%d %H:%M:%f', 'now')"
    }
    sorted_keys = list(sorted(to_insert.keys()))
    placeholders = ','.join(['?' for i in range(len(to_insert))]) # ?, ?, ?, ?
    values = tuple([to_insert[key] for key in sorted_keys])
    stmt = "INSERT INTO {tablename} ({columns}) VALUES ({placeholders})".format(
                tablename = __TABLE_NAME, columns=','.join(sorted_keys), placeholders=placeholders)
    c.execute(stmt, values)

    __conn.commit()
    c.close()

def _select():
    global __conn
    assert(__conn)
    c = __conn.cursor()
    result_columns = ','.join(MemfsLog.columns())
    select = '''SELECT {columns} FROM {tablename} LIMIT 1'''.format(columns = result_columns, tablename=__TABLE_NAME)
    ret = []
    c.execute(select)

    '''
    for row in c:
        ret.append(
            dict(zip(MemfsLog.columns(), map(lambda field: getField(row, field), MemfsLog.columns())))
        )
    '''
    if c.rowcount:
        def getField(row, field):
                value = row[MemfsLog.columns().index(field)]
                to_unpickle = [MemfsLog.PARAMS, MemfsLog.OUTPUT]
                if field in to_unpickle:
                    # sqlite3 returns unicode, and pickle expects str
                    # hopefully we won't have problems with this
                    value = pickle.loads(str(value))
                return value

        row = c.fetchone()
        return dict(zip(MemfsLog.columns(), map(lambda field: getField(row, field), MemfsLog.columns())))

    return None
