from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred, inlineCallbacks

from tubes.protocol import flowFountFromEndpoint
from tubes.listening import Listener
from tubes.tube import tube, series

@tube
class Reverser(object):
    def received(self, item):
        yield b"".join(reversed(item))

def reverseFlow(flow):
    from tubes.framing import bytesToLines, linesToBytes
    lineReverser = series(bytesToLines(), Reverser(), linesToBytes())
    flow.fount.flowTo(lineReverser).flowTo(flow.drain)

@inlineCallbacks
def main(reactor, listenOn="stdio:"):
    endpoint = serverFromString(reactor, listenOn)
    flowFount = yield flowFountFromEndpoint(endpoint)
    flowFount.flowTo(Listener(reverseFlow))
    yield Deferred()

if __name__ == '__main__':
    from twisted.internet.task import react
    from sys import argv
    react(main, argv[1:])
