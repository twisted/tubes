# -*- test-case-name: tubes.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utilities for testing L{tubes}.
"""

from zope.interface import Interface, implementer
from zope.interface.verify import verifyClass

from twisted.test.proto_helpers import StringTransport
from twisted.internet.defer import succeed
from twisted.internet.interfaces import (
    IStreamClientEndpoint, IStreamServerEndpoint, IListeningPort, IPushProducer
)

from ..itube import IDrain, IFount, IDivertable
from ..tube import tube
from ..kit import Pauser, beginFlowingFrom, beginFlowingTo

from twisted.internet.defer import Deferred

@implementer(IStreamClientEndpoint)
class StringEndpoint(object):
    """
    A client endpoint which connects to a L{StringTransport}.
    """
    def __init__(self):
        """
        Initialize the list of connected transports.
        """
        self.transports = []


    def connect(self, factory):
        """
        Connect the given L{IProtocolFactory} to a L{StringTransport} and
        return a fired L{Deferred}.

        @param factory: see L{IStreamClientEndpoint}

        @return: see L{IStreamClientEndpoint}
        """
        protocol = factory.buildProtocol(None)
        transport = StringTransport()
        transport.protocol = protocol
        protocol.makeConnection(transport)
        self.transports.append(transport)
        return succeed(protocol)



class IFakeOutput(Interface):
    """
    A sample interface to be used as an output marker for a fount.
    """



class IFakeInput(Interface):
    """
    A sample interface to be used as an input marker for a drain.
    """



@implementer(IFakeInput)
class FakeInput(object):
    """
    An implementation of a sample interface.
    """



@implementer(IDrain)
class FakeDrain(object):
    """
    Implements a fake IDrain for testing.

    @ivar received: All items that have thus far been received.
    @type received: L{list}

    @ivar stopped: All reasons that C{flowStopped} has been called with.
    @type stopped: L{list}
    """

    fount = None

    def __init__(self, inputType=None):
        self.received = []
        self.stopped = []
        self.inputType = inputType


    def flowingFrom(self, fount):
        """
        Set the C{fount} attribute.

        @param fount: see L{IDrain}
        """
        beginFlowingFrom(self, fount)


    def receive(self, item):
        """
        Append an item to L{FakeDrain.received}.

        @param item: see L{IDrain}
        """
        if self.fount is None:
            raise RuntimeError(
                "Invalid state: can't call receive on a drain "
                "when it's got no fount.")
        self.received.append(item)


    def flowStopped(self, reason):
        """
        The flow was stopped, record C{reason} in L{FakeDrain.stopped}.

        @param reason: see L{IDrain}
        """
        self.stopped.append(reason)


verifyClass(IDrain, FakeDrain)



@implementer(IFount)
class FakeFount(object):
    """
    Fake fount implementation for testing.
    """
    drain = None

    flowIsPaused = 0
    flowIsStopped = False
    def __init__(self, outputType=None):
        self._pauser = Pauser(self._actuallyPause, self._actuallyResume)
        self.outputType = outputType


    def flowTo(self, drain):
        """
        Record C{self.drain} and return its L{IDrain.flowingFrom} result.

        @param drain: see L{IFount}

        @return: see L{IFount}
        """
        # Either fount or drain may break the cycle, but it must inform its
        # peer by calling flowingFrom() or flowTo() with None so that they can
        # give up any resources associated with its peer, most especially the
        # drain letting go of pauses.
        return beginFlowingTo(self, drain)


    def pauseFlow(self):
        """
        Record C{self.drain} and return its L{IDrain.flowingFrom} result.

        @param drain: see L{IFount}

        @return: see L{IFount}
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        Record that the flow was stopped by setting C{flowIsStopped}.
        """
        self.flowIsStopped = True


    def _actuallyPause(self):
        """
        Pause the flow (incrementing flowIsPaused).

        @note: this is overridden in subclasses to modify behavior.
        """
        self.flowIsPaused += 1


    def _actuallyResume(self):
        """
        Resume the flow (decrementing flowIsPaused).

        @note: this is overridden in subclasses to modify behavior.
        """
        self.flowIsPaused -= 1


verifyClass(IFount, FakeFount)



@tube
class TesterTube(object):
    """
    Tube for testing that records its inputs.
    """

    def __init__(self):
        """
        Initialize structures for recording.
        """
        self.allReceivedItems = []


    def received(self, item):
        """
        Recieved an item, remember it.

        @param item: see L{ITube}
        """
        self.allReceivedItems.append(item)



@implementer(IDivertable)
class JustProvidesSwitchable(TesterTube):
    """
    A L{TesterTube} that just provides L{IDivertable} for tests that want
    to assert about interfaces (no implementation actually provided).
    """



@tube
@implementer(IDivertable)
class ReprTube(object):
    """
    A L{tubes.tube.tube} with a deterministic C{repr} for testing.
    """
    def __repr__(self):
        return '<Tube for Testing>'



@implementer(IDivertable)
@tube
class PassthruTube(object):
    """
    A L{tubes.tube.tube} which yields all of its input.
    """
    def received(self, data):
        """
        Produce all inputs as outputs.

        @param data: see L{IDivertable}
        """
        yield data


    def reassemble(self, data):
        """
        Reassemble any buffered outputs as inputs by simply returning them;
        valid since this tube takes the same input and output.

        @param data: see L{IDivertable}

        @return: C{data}
        """
        return data



class FakeFountWithBuffer(FakeFount):
    """
    Probably this should be replaced with a C{MemoryFount}.
    """
    def __init__(self):
        super(FakeFountWithBuffer, self).__init__()
        self.buffer = []


    def bufferUp(self, item):
        """
        Buffer items for delivery on the next resume or flowTo.

        @param item: see L{IFount}
        """
        self.buffer.append(item)


    def flowTo(self, drain):
        """
        Flush buffered items to the given drain as long as we're not paused.
        """
        result = super(FakeFountWithBuffer, self).flowTo(drain)
        self._go()
        return result


    def _actuallyResume(self):
        """
        Resume and unbuffer any items as long as we're not paused.
        """
        super(FakeFountWithBuffer, self)._actuallyResume()
        self._go()


    def _go(self):
        """
        Unbuffer any items as long as we're not paused.
        """
        while not self.flowIsPaused and self.buffer:
            item = self.buffer.pop(0)
            self.drain.receive(item)



@tube
class NullTube(object):
    """
    An L{ITube} that does nothing when inputs are received.
    """



@implementer(IListeningPort, IPushProducer)
class FakeListeningProducerPort(object):
    """
    This is a fake L{IListeningPort}, also implementing L{IPushProducer}, which
    L{flowFountFromEndpoint} needs to make backpressure work.
    """
    def __init__(self, factory):
        """
        Create a L{FakeListeningProducerPort} with the given protocol
        factory.
        """
        self.factory = factory
        self.stopper = Deferred()
        self.listenStopping = False
        self.currentlyProducing = True


    def pauseProducing(self):
        """
        Pause producing new connections.
        """
        self.currentlyProducing = False


    def resumeProducing(self):
        """
        Resume producing new connections.
        """
        self.currentlyProducing = True


    def startListening(self):
        """
        Start listening on this port.

        @raise CannotListenError: If it cannot listen on this port (e.g., it is
            a TCP port and it cannot bind to the required port number).
        """


    def stopListening(self):
        """
        Stop listening on this fake port.

        @return: a L{Deferred} that should be fired when the test wants to
            complete stopping listening.
        """
        self.listenStopping = True
        return self.stopper


    def stopProducing(self):
        """
        Stop producing more data.
        """
        self.stopListening()


    def getHost(self):
        """
        Get the host that this port is listening for.

        @return: An L{IAddress} provider.
        """

verifyClass(IListeningPort, FakeListeningProducerPort)
verifyClass(IPushProducer, FakeListeningProducerPort)


@implementer(IStreamServerEndpoint)
class FakeEndpoint(object):
    """
    A fake implementation of L{IStreamServerEndpoint} with a L{Deferred} that
    fires controllably.

    @ivar _listening: deferreds that will fire with listening ports when their
        C{.callback} is invoked (input to C{.callback} ignored); added to when
        C{listen} is called.
    @type _listening: L{list} of L{Deferred}

    @ivar _ports: list of ports that have already started listening
    @type _ports: L{list} of L{IListeningPort}
    """
    def __init__(self):
        """
        Create a L{FakeEndpoint}.
        """
        self._listening = []
        self._ports = []


    def listen(self, factory):
        """
        Listen with the given factory.

        @param factory: The factory to use for future connections.

        @return: a L{Deferred} that fires with a new listening port.
        """
        self._listening.append(Deferred())
        def newListener(ignored):
            result = FakeListeningProducerPort(factory)
            self._ports.append(result)
            return result
        return self._listening[-1].addCallback(newListener)



def fakeEndpointWithPorts():
    """
    Create a L{FakeEndpoint} and expose the list of ports that it uses.

    @return: a fake endpoint and a list of the ports it has listened on
    @rtype: a 2-tuple of C{(endpoint, ports)}, where C{ports} is a L{list} of
        L{IListeningPort}.
    """
    self = FakeEndpoint()
    return self, self._ports

verifyClass(IStreamServerEndpoint, FakeEndpoint)
