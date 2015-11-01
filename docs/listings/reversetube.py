from tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred
from tubes.tube import tube, series

@tube
class Reverser(object):
    def received(self, item):
        yield b"".join(reversed(item))

def reverseFlow(fount, drain):
    from tubes.framing import bytesToLines, linesToBytes
    lineReverser = series(bytesToLines(), Reverser(), linesToBytes())
    fount.flowTo(lineReverser).flowTo(drain)

def main(reactor, listenOn="stdio:"):
    endpoint = serverFromString(reactor, listenOn)
    endpoint.listen(factoryFromFlow(reverseFlow))
    return Deferred()

if __name__ == '__main__':
    from twisted.internet.task import react
    from sys import argv
    react(main, argv[1:])
