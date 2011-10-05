from commport import Port
from time import *
import time
import threading

class TimeController(object):
    '''Object of this class is used by test suite to set current time'''
    def __init__(self, outUnixAddr, inUnixAddr):
        self._inOutPort = Port(outUnixAddr, inUnixAddr)
        self.finished = False
        self.timeReturn = 17

    def initialize(self):
        self._inOutPort.initialize()

    def finalize(self):
        self.finished = True

    def dispose(self):
	print("TimeController::dispose()" + `self._inOutPort`)
        self._inOutPort.dispose()

    def handle(self, event):
        print("TimeController::Handle()")
        args = event['args']
        kw = event['kw']
        method = event['method']
        print("TimeController::Handle2()")
        try:
            ret = getattr(self, method)(*args, **kw)
            print("ret1: " + str(ret))
        except Exception, e:
            ret = getattr(time, method)(*args, **kw)
            print("ret2: " + str(ret))

        return self._inOutPort.send(ret)

    def time(self):
        return self.timeReturn

    def loop(self):
        print("TimeController::loop()")
        while not self.finished:
            try:
                event = self._inOutPort.receive(0.001)
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
        try:
            return getattr(self, item)
        except Exception, e:
            def rpcWrapper(*args, **kw):
                operation = item
                self._inOutPort.send({'method' : 'time', 'args' : [], 'kw' : {}})
                ret = self._inOutPort.receive(1.0)
                return ret
            return rpcWrapper

class ModuleInterface(object):

    TIME_CONTROLLER_PORT_ADDR = 'TimeController.sock'
    TIME_MOCK_PORT_ADDR = 'TimeMock.sock'

    def __init__(self):
        controllerPort = ModuleInterface.TIME_CONTROLLER_PORT_ADDR
        mockPort = ModuleInterface.TIME_MOCK_PORT_ADDR
        self.timeController = TimeController(outUnixAddr=mockPort, inUnixAddr=controllerPort)
        self.timeMock = TimeMock(outUnixAddr=controllerPort, inUnixAddr=mockPort)
        self.server = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, tback):
        self.timeController.finalize()

    @staticmethod
    def runController(timeController):
        timeController.initialize()
        timeController.loop()

    def getController(self):
        self.server = threading.Thread(target=ModuleInterface.runController, args=(self.timeController,))
        self.server.setDaemon(False)
        self.server.start()
        return self.timeController

    def initialize(self):
        self.timeMock.initialize()

    def time(self):
        t = self.timeMock.time()
        print("Time() gonna return " + str(t))
        return t
