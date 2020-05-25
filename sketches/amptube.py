from zope.interface import implementer

from twisted.internet.endpoints import serverFromString, clientFromString

from twisted.internet.defer import Deferred, inlineCallbacks

from twisted.internet.protocol import Factory
from twisted.protocols.amp import AmpBox, Command, IBoxSender, Integer, AMP, CommandLocator, BoxDispatcher

from tubes.protocol import flowFountFromEndpoint
from tubes.listening import Listener
from tubes.itube import ISegment
from tubes.tube import tube, series
from tubes.framing import bytesToIntPrefixed

@tube
class StringsToBoxes:

    inputType = None            # I... Packet? IString? IDatagram?
    outputType = None           # AmpBox -> TODO, implement classes.

    state = 'new'

    def received(self, item):
        return getattr(self, 'received_' + self.state)(item)


    def received_new(self, item):
        self._currentBox = AmpBox()
        return self.received_key(item)


    def received_key(self, item):
        if item:
            self._currentKey = item
            self.state = 'value'
        else:
            self.state = 'new'
            yield self._currentBox


    def received_value(self, item):
        self._currentBox[self._currentKey] = item
        self.state = 'key'



@tube
class BoxesToData:
    """
    Shortcut: I want to go from boxes directly to data.
    """
    inputType = None            # AmpBox
    outputType = ISegment

    def received(self, item):
        yield item.serialize()


@implementer(IBoxSender)
class BufferingBoxSender(object):
    def __init__(self):
        self.boxesToSend = []

    def sendBox(self, box):
        self.boxesToSend.append(box)

    def unhandledError(failure):
        from twisted.python import log
        log.err(failure)


@tube
class BoxConsumer:

    inputType = None            # AmpBox
    outputType = None           # AmpBox

    def __init__(self, boxReceiver):
        self.boxReceiver = boxReceiver
        self.bbs = BufferingBoxSender()


    def started(self):
        self.boxReceiver.startReceivingBoxes(self.bbs)


    def unhandledError(self, failure):
        failure.printTraceback()


    def received(self, box):
        self.boxReceiver.ampBoxReceived(box)
        boxes = self.bbs.boxesToSend
        self.bbs.boxesToSend = []
        return boxes



class Add(Command):
    arguments = [(b'a', Integer()),
                 (b'b', Integer())]
    response = [(b'result', Integer())]


class Math(CommandLocator):
    @Add.responder
    def add(self, a, b):
        return dict(result=a + b)


def mathFlow(flow):
    byteParser = bytesToIntPrefixed(16)
    messageParser = StringsToBoxes()
    applicationCode = Math()
    dispatcher = BoxDispatcher(applicationCode)
    messageConsumer = BoxConsumer(dispatcher)
    messageSerializer = BoxesToData()
    combined = series(
        byteParser, messageParser, messageConsumer, messageSerializer, flow.drain
    )
    flow.fount.flowTo(combined)



@inlineCallbacks
def main(reactor, type="server"):
    if type == "server":
        serverEndpoint = serverFromString(reactor, "tcp:1234")
        flowFount = yield flowFountFromEndpoint(serverEndpoint)
        flowFount.flowTo(Listener(mathFlow))
    else:
        clientEndpoint = clientFromString(reactor, "tcp:localhost:1234")
        amp = yield clientEndpoint.connect(Factory.forProtocol(AMP))
        for x in range(20):
            print((yield amp.callRemote(Add, a=1, b=2)))
    yield Deferred()


from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
