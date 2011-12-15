import logging
import os
import traceback
import inspect
import datetime

__initialized = False
debug = False

currentLine = 0
depth = 0
offset = ''

def time_file_line_prefix(f):
    def wrapper(msg, filename=None, line=None):
        global offset
        global currentLine

        currentLine += 1
        invoker = inspect.getouterframes(inspect.currentframe())[1]
        if filename is None:
            filename = invoker[1]
            filename = os.path.basename(filename)
        if line is None:
            line = invoker[2]

        now = datetime.datetime.now()
        msg_lines = str(msg).split('\n')
        if not msg_lines[-1]:
            del msg_lines[-1]
        for msg_line in msg_lines:
            s = '{line:<6}{time} # {fileline:<21}|{offset}{msg}'.format(
                line=currentLine,
                time='{0:>2}.{1:>2}.{2:>2}:{3:>6}'.format(now.hour, now.minute, now.second, now.microsecond),
                fileline=filename + ":" + str(line),
                offset=offset,
                msg=str(msg_line))
            f(s)
    return wrapper

@time_file_line_prefix
def DEBUG(msg):
    logging.debug(msg)

@time_file_line_prefix
def INFO(msg):
    logging.info(msg)

@time_file_line_prefix
def ERROR(msg):
    logging.error(msg)

def enableDebug():
    global debug
    debug = True

def initialize(logfile='logs/LOG'):

    global __initialized

    dirname = os.path.dirname(logfile)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)

    if os.path.exists(logfile):
        os.remove(logfile)

    FORMAT="%(message)s"
    logging.basicConfig(filename=logfile,level=logging.DEBUG,format=FORMAT)

    __initialized = True

def NO_LOG(msg):
    pass

#ERROR, DEBUG, INFO = NO_LOG, NO_LOG, NO_LOG

def trace(f):
    def callWrapper(*args, **kw):
        global depth
        global offset
        global debug
        if not debug:
            return f(*args, **kw)

        try:
            class_name = args[0].__class__.__name__
            func_name = f.func_name
            invoker = inspect.getouterframes(inspect.currentframe())[1]
            curr_filename = os.path.basename(invoker[1])
            curr_line = invoker[2]
            previous_line = curr_line
            depth += 1
            offset = depth * "\t"
            s = str("{%s- %s.%s(args: %s, kw: %s)" %
                          (depth, class_name, func_name, args[1:], kw))
            DEBUG(s, curr_filename, curr_line)
            retval = f(*args, **kw)
            s = str("-%s} %s.%s(...) -> returns: %s(%r)" %
                          (depth, class_name, func_name, type(retval), retval))
            DEBUG(s, curr_filename, curr_line)
            curr_line = previous_line
            depth -= 1
            offset = depth * "\t"
            return retval
        except Exception, inst:
            ERROR("function: %s, exception: %r" % (f.func_name, inst))
            exc_traceback = traceback.format_exc()
            ERROR("Exception traceback: %s" % exc_traceback)
            raise inst

    return callWrapper
