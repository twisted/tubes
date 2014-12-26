
import os

from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.internet.defer import Deferred

def main(reactor, listen="tcp:4321", connect="tcp:localhost:6543"):
    clientEndpoint = clientFromString(reactor, connect)
    serverEndpoint = serverFromString(reactor, listen)

    def incomingTubeFactory(listeningFount, listeningDrain):
        def outgoingTubeFactory(connectingFount, connectingDrain):
            listeningFount.flowTo(connectingDrain)
            connectingFount.flowTo(listeningDrain)
        clientEndpoint.connect(factoryFromFlow(outgoingTubeFactory))

    serverEndpoint.listen(factoryFromFlow(incomingTubeFactory))
    return Deferred()

from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
