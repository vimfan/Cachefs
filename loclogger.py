import logging
import os
import traceback

__initialized = False
debug = False

depth = 0
offset = 0
curr_filename = ''
curr_line = ''

def _DEBUG_IMPL(msg):
    logging.debug(msg)

def DEBUG(msg):
    global curr_filename
    global curr_line
    global offset
    s = ''.join(["#", str(curr_filename), ":", str(curr_line), str(offset), str(msg)])
    _DEBUG_IMPL(s)

def INFO(msg):
    logging.info(msg)

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

    FORMAT="%(asctime)-15s %(message)s"
    logging.basicConfig(filename=logfile,level=logging.DEBUG,format=FORMAT)

    __initialized = True

def NO_LOG(msg):
    pass

#ERROR, DEBUG, INFO = NO_LOG, NO_LOG, NO_LOG

def method_logger(f):
    def wrapper(*args, **kw):
        global depth
        global offset
        global curr_filename
        global curr_line
        try:
            class_name = args[0].__class__.__name__
            func_name = f.func_name
            curr_filename = os.path.basename(f.func_code.co_filename)
            curr_line = f.func_code.co_firstlineno
            depth += 1
            offset = depth * "\t"
            s = str("{%s- %s.%s(args: %s, kw: %s)" %
                          (depth, class_name, func_name, args[1:], kw))
            DEBUG(s)
            retval = f(*args, **kw)
            s = str("-%s} %s.%s(...) -> returns: %s(%r)" %
                          (depth, class_name, func_name, type(retval), retval))
            DEBUG(s)
            depth -= 1
            offset = depth * "\t"
            return retval
        except Exception, inst:
            ERROR("function: %s, exception: %r" % (f.func_name, inst))
            exc_traceback = traceback.format_exc()
            ERROR("Exception traceback: %s" % exc_traceback)
            raise inst
    return wrapper
