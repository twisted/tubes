from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred

def echoFlow(fount, drain):
    fount.flowTo(drain)

def main(reactor, listenOn="stdio:"):
    endpoint = serverFromString(reactor, listenOn)
    endpoint.listen(factoryFromFlow(echoFlow))
    return Deferred()

from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
