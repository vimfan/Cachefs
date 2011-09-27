import logging
import os
import traceback

__initialized = False
debug = False

def DEBUG(msg):
    logging.debug(msg)

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

    logging.basicConfig(filename=logfile,level=logging.DEBUG,)

    __initialized = True

def NO_LOG(msg):
    pass

#ERROR, DEBUG, INFO = NO_LOG, NO_LOG, NO_LOG

depth = 0
def method_logger(f):
    def wrapper(*args, **kw):
        global depth
        try:
            class_name = args[0].__class__.__name__
            func_name = f.func_name
            depth += 1
            DEBUG("%s:%s {%s- %s.%s(args: %s, kw: %s)" %
                          (f.func_code.co_filename,
                           f.func_code.co_firstlineno,
                           depth,
                           class_name, func_name,
                           args[1:], kw))
            retval = f(*args, **kw)
            DEBUG("%s:%s -%s} %s.%s(...) -> returns: %s(%r)" %
                          (f.func_code.co_filename,
                           f.func_code.co_firstlineno,
                           depth,
                           class_name, func_name, type(retval), retval))
            depth -= 1
            return retval
        except Exception, inst:
            ERROR("function: %s, exception: %r" % (f.func_name, inst))
            exc_traceback = traceback.format_exc()
            ERROR("Exception traceback: %s" % exc_traceback)
            raise inst
    return wrapper
