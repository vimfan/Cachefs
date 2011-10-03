import threading
import socket
import SocketServer
import Queue
import time
import os

import pickle
import StringIO

class OutPort(object):

    class ConnectionError(Exception):
        pass

    def __init__(self, unixPort):
        self.__socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.__unixPort = unixPort

    def __del__(self):
        self.__socket.close()

    def connect(self):
        for i in range(50):
            try:
                self.__socket.connect(self.__unixPort)
                return
            except:
                time.sleep(0.05)
        raise OutPort.ConnectionError() 

    def send(self, event):
        try:
            pickledEvent = pickle.dumps(event)
            # sizeOfEvent in 4 bytes, then SerializedEvent
            self.__socket.send(''.join(['%04d' % len(pickledEvent), pickledEvent]))
        except Exception, e: # FIXME
            print(str(e))

class InPort(object):

    class Timeout(Exception):
        pass

    def __init__(self, unixPort):
        self.eventQueue = Queue.Queue()
        self.__unixPort = unixPort
        self.server = InPort.StreamServer(self.eventQueue, self.__unixPort)

    def __del__(self):
        self.server.shutdown()
        os.remove(self.__unixPort)

    def listen(self):
        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        serverThread = threading.Thread(target=self.server.serve_forever)
        # Exit the server thread when the main thread terminates
        serverThread.setDaemon(False)
        serverThread.start()

    def receive(self, timeout = None):
        '''If timeout is set to non-zero, then this invocation will be blocking'''
        try:
            return self.eventQueue.get(block=(not timeout is None), timeout=timeout)
        except Queue.Empty, e:
            raise InPort.Timeout("Event not received")

    class StreamServer(SocketServer.ThreadingUnixStreamServer):

        def __init__(self, eventQueue, unixPort):
            SocketServer.ThreadingUnixStreamServer.__init__(self, unixPort, InPort.EventHandler)
            self.eventQueue = eventQueue

    class EventHandler(SocketServer.BaseRequestHandler):

        def handle(self):
            while True:
                data = ''
                buffer_size_str = self.request.recv(4)
                if not buffer_size_str:
                    break

                buffer_size = int(buffer_size_str)
                read_buffer = self.request.recv(buffer_size)
                if read_buffer:
                    data = ''.join([data, read_buffer])

                dataStream = StringIO.StringIO(data)
                try:
                    event = pickle.load(dataStream)
                    self.server.eventQueue.put(event)
                except Exception, e: # FIXME
                    print(str(e))

class Port(InPort, OutPort):

    def __init__(self, outPort, inPort):
        InPort.__init__(self, inPort)
        OutPort.__init__(self, outPort)

    def __del__(self):
        OutPort.__del__(self)
        InPort.__del__(self)

    def initialize(self):
        self.listen()
        self.connect()

