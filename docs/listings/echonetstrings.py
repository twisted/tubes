from tubes.tube import Tube
from tubes.framing import stringsToNetstrings
from tubes.protocol import flowFountFromEndpoint
from tubes.listening import Listener

from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.defer import inlineCallbacks, Deferred()

def echoTubeFactory(flow):
    return (flow.fount.flowTo(Tube(stringsToNetstrings()))
                      .flowTo(flow.drain))

@inlineCallbacks
def main(reactor):
    endpoint = TCP4ServerEndpoint(reactor, 4321)
    flowFount = yield flowFountFromEndpoint(endpoint)
    flowFount.flowTo(Listener(echoTubeFactory))
    yield Deferred()

if __name__ == '__main__':
    from twisted.internet.task import react
    react(main, [])
