from commport import Port
from time import *
import time
import threading

class TimeController(object):
    '''Object of this class is used by test suite to set current time'''
    def __init__(self, unixAddr1, unixAddr2):
        self._inOutPort = Port(unixAddr1, unixAddr2)
        self.finished = False
        self.timeReturn = 17

    def initialize(self):
        self._inOutPort.initialize()

    def finalize(self):
        self.finished = True

    def handle(self, event):
        args = event['args']
        kw = event['kw']
        method = event['method']
        try:
            ret = getattr(self, method)(*args, **kw)
        except Exception, e:
            ret = getattr(time, method)(*args, **kw)

        return self._inOutPort.send(ret)

    def time(self):
        return self.timeReturn

    def loop(self):
        while not self.finished:
            try:
                event = self._inOutPort.receive(0.001)
                self.handle(event)
            except:
                pass

class TimeMock(object):
    '''Object of this class encapsulates original time module interface'''
    def __init__(self, unixAddr1, unixAddr2):
        self._inOutPort = Port(unixAddr1, unixAddr2)

    def initialize(self):
        self._inOutPort.initialize()

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

    TIMER1_PORT_ADDR = 'TimeMock1.sock'
    TIMER2_PORT_ADDR = 'TimeMock2.sock'

    def __init__(self):
        port1 = ModuleInterface.TIMER1_PORT_ADDR
        port2 = ModuleInterface.TIMER2_PORT_ADDR
        self.timeController = TimeController(port1, port2)
        self.timeMock = TimeMock(port2, port1)
        self.server = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, tback):
        self.timeController.finalize()

    @staticmethod
    def runController(timeController):
        timeController.initialize()
        timeController.loop()

    def initialize(self):
        self.server = threading.Thread(target=ModuleInterface.runController, args=(self.timeController,))
        self.server.setDaemon(False)
        self.server.start()

        self.timeMock.initialize()

    def time(self):
        return self.timeMock.time()

