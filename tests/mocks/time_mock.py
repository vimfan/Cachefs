from commport import Port
from time import *
import time
import threading
import sys

class TimeController(object):
    '''Object of this class is used by test suite to set current time'''
    def __init__(self, outUnixAddr, inUnixAddr):
        self._inOutPort = Port(outUnixAddr, inUnixAddr)
        self.finished = False
        self.timeReturn = 17
        self._lock = threading.Lock()

    def initialize(self):
        self._inOutPort.initialize()

    def finalize(self):
        self.finished = True

    def dispose(self):
        print("TimeController::dispose()" + `self._inOutPort`)
        self._inOutPort.dispose()

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

    def handle(self, event):
        args = event['args']
        kw = event['kw']
        method = event['method']
        try:
            self._lock.acquire()
            ret = getattr(self, method)(*args, **kw)
            print("TimeMock::" + method + "(...) -> {ret}".format(ret=str(ret)))
        except Exception, e:
            ret = getattr(time, method)(*args, **kw)
            print("time." + method + "(...) -> " + str(ret))
        finally:
            self._lock.release()

        return self._inOutPort.send(ret)

    def time(self):
        return self._timeImpl()

    def _timeImpl(self):
        return self.timeReturn


    def loop(self):
        while not self.finished:
            try:
                event = self._inOutPort.receive(0.1)
                self.handle(event)
            except:
                pass

class TimeMock(object):
    '''Object of this class encapsulates original time module interface'''
    def __init__(self, outUnixAddr, inUnixAddr):
        self._inOutPort = Port(outUnixAddr, inUnixAddr)

    def initialize(self):
        self._inOutPort.initialize()

    def dispose(self):
        self._inOutPort.dispose()

    def __getattr__(self, item):
        if hasattr(time, item):
            def rpcWrapper(*args, **kw):
                operation = item
                self._inOutPort.send({'method' : item, 'args' : args, 'kw' : kw})
                ret = self._inOutPort.receive(2.0)
                return ret
            return rpcWrapper
        return getattr(self, item)

class ModuleInterface(object):

    TIME_CONTROLLER_PORT_ADDR = 'TimeController.sock'
    TIME_MOCK_PORT_ADDR = 'TimeMock.sock'

    def __init__(self):
        controllerPort = ModuleInterface.TIME_CONTROLLER_PORT_ADDR
        mockPort = ModuleInterface.TIME_MOCK_PORT_ADDR
        self.timeController = TimeController(outUnixAddr=mockPort, inUnixAddr=controllerPort)
        self.timeMock = TimeMock(outUnixAddr=controllerPort, inUnixAddr=mockPort)
        self.server = None

    @staticmethod
    def _runController(timeController):
        timeController.initialize()
        timeController.loop()

    def getController(self):
        if not self.server:
            self.server = threading.Thread(target=ModuleInterface._runController, args=(self.timeController,))
            self.server.setDaemon(False)
            self.server.start()
        return self.timeController

    def __getattr__(self, item):
        if hasattr(self.timeMock, item):
            return getattr(self.timeMock, item)
        return getattr(self, item)
