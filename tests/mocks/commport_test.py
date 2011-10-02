import unittest
import threading
import socket
import pickle

import os
from commport import Port, OutPort, InPort

class OutPortTest(unittest.TestCase):

    UNIX_SOCKET_ADDR = 'OutPortTest.sock'

    def serverHelper(self, eventToMatch):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(OutPortTest.UNIX_SOCKET_ADDR)
        sock.listen(1)
        (connection, address) = sock.accept()
        receivedSize = int(connection.recv(4))

        receivedEvent = connection.recv(receivedSize)
        connection.close()
        sock.close()

        os.remove(OutPortTest.UNIX_SOCKET_ADDR)

        self.assertEqual(receivedSize, len(eventToMatch))
        self.assertEqual(eventToMatch, receivedEvent) 

    def test_outPort(self):
        eventToSend = ['foo']

        server = threading.Thread(target=OutPortTest.serverHelper, args=(self, pickle.dumps(eventToSend)))
        server.setDaemon(True)
        server.start()

        outPort = OutPort(OutPortTest.UNIX_SOCKET_ADDR)
        outPort.connect()
        outPort.send(eventToSend)

        server.join()

    def tearDown(self):
        pass

class InPortTest(unittest.TestCase):

    UNIX_SOCKET_ADDR = 'InPortTest.sock'

    def setUp(self):
        pass

    def test_simple(self):
        inPort = InPort(InPortTest.UNIX_SOCKET_ADDR)
        inPort.listen()

        outPort = OutPort(InPortTest.UNIX_SOCKET_ADDR)
        outPort.connect()

        eventsToSent = ['one', 'two', 3, 4.0, u'five']
        for event in eventsToSent:
            outPort.send(event)

        for event in eventsToSent:
            eventReceived = inPort.receive(1.0)
            self.assertEqual(event, eventReceived)

    def test_manyEvents(self):
        inPort = InPort(InPortTest.UNIX_SOCKET_ADDR)
        inPort.listen()

        outPort = OutPort(InPortTest.UNIX_SOCKET_ADDR)
        outPort.connect()

        eventsToSent = range(1000)
        for event in eventsToSent:
            outPort.send(event)

        for event in eventsToSent:
            eventReceived = inPort.receive(1.0)
            self.assertEqual(event, eventReceived)

    def tearDown(self):
        pass

class PortTest(unittest.TestCase):

    UNIX_FIRST_ADDR = 'PortTestFirst.sock'
    UNIX_SECOND_ADDR = 'PortTestSecond.sock'

    def setUp(self):
        pass

    def test_inOutPort_basic(self):

        inPort = InPort(PortTest.UNIX_FIRST_ADDR)
        inOutPort = Port(PortTest.UNIX_FIRST_ADDR, PortTest.UNIX_SECOND_ADDR)
        outPort = OutPort(PortTest.UNIX_SECOND_ADDR)

        inOutPort.initialize()
        inPort.listen()
        outPort.connect()

        event = 'foo'
        outPort.send(event)
        self.assertEqual(event, inOutPort.receive(1.0))

        event2 = 'bar'
        inOutPort.send(event2)
        self.assertEqual(event2, inPort.receive(1.0))

    def tearDown(self):
        pass
