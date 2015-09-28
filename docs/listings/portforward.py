from tubes.protocol import flowFountFromEndpoint, flowFromEndpoint
from tubes.listening import Listener

from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.internet.defer import Deferred, inlineCallbacks

@inlineCallbacks
def main(reactor, listen="tcp:4321", connect="tcp:localhost:6543"):
    clientEndpoint = clientFromString(reactor, connect)
    serverEndpoint = serverFromString(reactor, listen)

    def incoming(listening):
        def outgoing(connecting):
            listening.fount.flowTo(connecting)
            connecting.fount.flowTo(listening.drain)
        flowFromEndpoint(clientEndpoint).addCallback(outgoing)
    flowFount = yield flowFountFromEndpoint(serverEndpoint)
    flowFount.flowTo(Listener(incoming))
    yield Deferred()

if __name__ == '__main__':
    from twisted.internet.task import react
    from sys import argv
    react(main, argv[1:])
