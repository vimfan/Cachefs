class FilesystemEvent(object):

    def __init__(self, time, operation, params, output):
        self.time = time
        self.operation = operation
        self.params = params
        self.output = output

    def __repr__(self):
        return "Event {time}: {operation}({params}) -> {output}".format(
            time=self.time, operation=self.operation,
            params=str(self.params), output=str(self.output))
