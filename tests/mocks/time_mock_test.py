import unittest
import threading
import pdb
import time as time_original
import time_mock

class TimeTest(unittest.TestCase):

    UNIX_ADDR_1 = 'TimeTest1.sock'
    UNIX_ADDR_2 = 'TimeTest2.sock'

    @staticmethod
    def timeControllerLoop(timeController):
        timeController.initialize()
        timeController.loop()

    def test_time(self):
        timeController = time_mock.TimeController(TimeTest.UNIX_ADDR_1, TimeTest.UNIX_ADDR_2)

        server = threading.Thread(target=TimeTest.timeControllerLoop, args=(timeController,))
        server.setDaemon(False)
        server.start()

        timeMock = time_mock.TimeMock(TimeTest.UNIX_ADDR_2, TimeTest.UNIX_ADDR_1)
        timeMock.initialize()

        for i in range(10):
            value = i + (0.01 * i)
            timeController.timeReturn = value
            self.assertEqual(value, timeMock.time())

        timeController.finalize()
        server.join()

    '''
    def test_timeModuleTest(self):
        iface = time_mock.ModuleInterface() 
        with iface:
            iface.initialize()

            timeController = iface.timeController

            timeValue = 9.9
            timeController.timeReturn = timeValue
            self.assertEqual(timeValue, iface.time())

            timeController.finished = True
    '''

