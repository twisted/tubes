from tubes.protocol import flowFountFromEndpoint
from tubes.listening import Listener

from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred, inlineCallbacks

def echo(flow):
    flow.fount.flowTo(flow.drain)

@inlineCallbacks
def main(reactor, listenOn="stdio:"):
    listener = Listener(echo)
    endpoint = serverFromString(reactor, listenOn)
    flowFount = yield flowFountFromEndpoint(endpoint)
    flowFount.flowTo(listener)
    yield Deferred()

if __name__ == '__main__':
    from twisted.internet.task import react
    from sys import argv
    react(main, argv[1:])
