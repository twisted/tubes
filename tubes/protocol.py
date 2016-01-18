# -*- test-case-name: tubes.test.test_protocol -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Objects to connect L{real data <_Protocol>} to L{tubes}.

@see: L{flowFountFromEndpoint}
"""

__all__ = [
    'flowFountFromEndpoint',
    'flowFromEndpoint',
]

from zope.interface import implementer, implementedBy

from .kit import Pauser, beginFlowingFrom, beginFlowingTo, OncePause
from .itube import StopFlowCalled, IDrain, IFount, ISegment
from .listening import Flow

from twisted.python.failure import Failure
from twisted.internet.interfaces import IPushProducer, IListeningPort
from twisted.internet.protocol import Protocol as _Protocol

if 0:
    # Workaround for inability of pydoctor to resolve references.
    from twisted.internet.interfaces import (
        IProtocol, ITransport, IConsumer, IProtocolFactory, IProducer,
        IStreamServerEndpoint
    )
    (IProtocol, ITransport, IConsumer, IProtocolFactory, IProducer,
     IStreamServerEndpoint)
    from twisted.internet.defer import Deferred
    Deferred



@implementer(IPushProducer)
class _FountProducer(object):
    """
    A L{_FountProducer} is an adapter to L{IPushProducer} for an L{IFount}.

    @ivar _fount: An L{IFount}.
    @type _fount: L{IFount}.

    @ivar _pause: A pause if the fount has been paused by C{pauseProducing}
    @type _pause: L{IPause} or L{types.NoneType}
    """
    def __init__(self, fount):
        self._fount = fount
        self._pause = None


    def pauseProducing(self):
        """
        The producer has been paused.  Ensure that the fount is paused.
        """
        # TODO: this implementation is (obviously) incorrect; we could lose
        # track of pauses.  Write some tests.
        self._pause = self._fount.pauseFlow()


    def resumeProducing(self):
        """
        The producer has been resumed.  Ensure that the fount is unpaused.
        """
        self._pause.unpause()


    def stopProducing(self):
        """
        Stop producing data.
        """
        self._fount.stopFlow()



@implementer(IDrain)
class _TransportDrain(object):
    """
    A L{_TransportDrain} is an L{IDrain} that wraps around an object that
    provides L{ITransport} and L{IConsumer}, and delivers data to that
    transport, and flow-control notifications from the consumer.

    @ivar _transport: The transport.
    @type _transport: L{IConsumer} / L{ITransport} provider.
    """

    fount = None
    inputType = ISegment

    def __init__(self, transport):
        self._transport = transport


    def flowingFrom(self, fount):
        """
        Data is flowing to this transport from the given fount.  Register that
        fount as the transport's producer.

        @param fount: the fount producing data - L{ISegment}s - for this
            transport.
        """
        if self.fount is not None:
            self._transport.unregisterProducer()
        beginFlowingFrom(self, fount)
        self._transport.registerProducer(_FountProducer(fount), True)


    def receive(self, item):
        """
        Receive an item of data, some bytes, from the fount.  Pass it along to
        the transport.

        @param item: a fragment of a stream of bytes.
        @type item: L{bytes}
        """
        self._transport.write(item)


    def flowStopped(self, reason):
        """
        The flow of data that should be written to the underlying transport has
        ceased.  Perform a half-close on the transport if possible so that it
        knows no further data is forthcoming.

        @param reason: the reason that the flow stopped; ignored.
        """
        # TODO: this should be loseWriteConnection.
        self._transport.loseConnection()



@implementer(IFount)
class _TransportFount(object):
    """
    An L{IFount} that wraps around an L{ITransport}, and, with the help of a
    L{_ProtocolPlumbing}, delivers any data received by that L{ITransport} to
    an L{IDrain}.

    @ivar _transport: the transport.
    @type _transport: provider of L{ITransport} and L{IProducer}.

    @ivar _pauser: a pauser that will pause and resume the transport.
    @type _pauser: L{Pauser}

    @ivar _preReceivePause: If data is received from the protocol when no drain
        is connected, this will be an L{IPause}.
    @type _preReceivePause: L{IPause} or L{types.NoneType}

    @ivar _preReceiveBuffer: If data is received from the protocol when no
        drain is connected, then this will be the bytes.
    @type _preReceiveBuffer: L{bytes} or L{types.NoneType}
    """

    drain = None
    outputType = ISegment

    def __init__(self, transport):
        self._transport = transport
        self._pauser = Pauser(self._transport.pauseProducing,
                              self._transport.resumeProducing)
        self._preReceivePause = None
        self._preReceiveBuffer = None


    def flowTo(self, drain):
        """
        Start delivering data from the transport to the given drain.

        @param drain: the drain that will receive data from the wrapped
            transport.

        @return: the next fount in the chain.
        """
        result = beginFlowingTo(self, drain)
        if self._preReceivePause is not None:
            self._preReceivePause.unpause()
            self.drain.receive(self._preReceiveBuffer)
            self._preReceiveBuffer = None
            self._preReceivePause = None
        return result


    def pauseFlow(self):
        """
        Pause flowing.

        @return: a L{pause token <IPause>}.
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        End the flow from this fount, dropping the TCP connection in the
        process.
        """
        # Really, stopFlow just ends the *read* connection, but there is no
        # such thing as "loseReadConnection" because TCP can't signal that.
        # This is of potential (academic?) future interest when considering
        # enhanced properties of subprocess transports, because you can both
        # trigger and detect the fact that a subprocess's stdin was closed.
        self._transport.loseConnection()



class _ProtocolPlumbing(_Protocol):
    """
    An adapter between an L{ITransport} and L{IFount} / L{IDrain} interfaces.

    A L{_ProtocolPlumbing} implements L{IProtocol} to deliver all incoming data
    to the drain associated with its L{fount <IFount>}.

    @ivar _flow: A flow function, as described in L{_factoryFromFlow}.
    @type _flow: L{callable}

    @ivar _drain: The drain that is passed on to the application, created after
        the connection is established in L{_ProtocolPlumbing.connectionMade}.
    @type _drain: L{_TransportDrain}

    @ivar _fount: The fount that is passed on to the application, created after
        the connection is established in L{_ProtocolPlumbing.connectionMade}.
    @type _fount: L{_TransportFount}
    """

    def __init__(self, flow):
        self._flow = flow


    def connectionMade(self):
        """
        The connection was established.  Create an L{IDrain} and an L{IFount}
        and give them to the flow function.
        """
        self._drain = _TransportDrain(self.transport)
        self._fount = _TransportFount(self.transport)
        self._flow(self._fount, self._drain)


    def dataReceived(self, data):
        """
        Some data was received.  Deliver it to the fount created in
        L{connectionMade}.

        @param data: The bytes that were received.
        @type data: L{bytes}
        """
        drain = self._fount.drain
        if drain is None:
            self._fount._preReceivePause = self._fount._pauser.pause()
            self._fount._preReceiveBuffer = data
            return
        drain.receive(data)


    def connectionLost(self, reason):
        """
        The connection was lost.

        If our fount is flowing to a drain, alert that drain that the flow was
        stopped.

        If our drain is flowing from a fount, alert that fount that it should
        stop flowing.

        @param reason: The reason that the connection was terminated.
        @type reason: L{Failure}
        """
        if self._fount.drain is not None:
            self._fount.drain.flowStopped(reason)
        if self._drain.fount is not None:
            self._drain.fount.stopFlow()



def _factoryFromFlow(flow):
    """
    Convert a flow function into an L{IProtocolFactory}.

    A "flow function" is a function which takes a L{fount <IFount>} and an
    L{drain <IDrain>}.

    L{_factoryFromFlow} takes such a function and creates an
    L{IProtocolFactory} which, upon each new connection, provides the flow
    function with an L{IFount} and an L{IDrain} representing the read end and
    the write end of the incoming connection, respectively.

    @param flow: a 2-argument callable, taking (fount, drain).
    @type flow: L{callable}

    @return: a protocol factory.
    @rtype: L{IProtocolFactory}
    """
    from twisted.internet.protocol import Factory
    return Factory.forProtocol(lambda: _ProtocolPlumbing(flow))



@implementer(IFount)
class _FountImpl(object):
    """
    Implementation of fount for listening port.
    """

    outputType = implementedBy(Flow)

    def __init__(self, portObject, aFlowFunction, preListen):
        """
        Create a fount implementation from a provider of L{IPushProducer} and a
        function that takes a fount and a drain.

        @param portObject: the result of the L{Deferred} from
            L{IStreamServerEndpoint.listen}
        @type portObject: L{IListeningPort} and L{IPushProducer} provider
            (probably; workarounds are in place for other cases)

        @param aFlowFunction: a 2-argument callable, invoked when a connection
            arrives, with a fount and drain.
        @type aFlowFunction: L{callable}

        @param preListen: the founts and drains accepted before the C{listen}
            L{Deferred} has fired.  Because these might be arriving before this
            L{_FountImpl} even I{exists}, this needs to be passed in.  That is
            OK because L{_FountImpl} is very tightly coupled to
            L{flowFountFromEndpoint}, which is the only thing that constructs
            it.
        @type preListen: L{list} of 2-L{tuple}s of C{(fount, drain)}
        """
        self.drain = None
        self._preListen = preListen
        self._pauser = Pauser(portObject.pauseProducing,
                              portObject.resumeProducing)
        self._noDrainPause = OncePause(self._pauser)
        self._aFlowFunction = aFlowFunction
        self._portObject = portObject
        if preListen:
            self._noDrainPause.pauseOnce()


    def flowTo(self, drain):
        """
        Start flowing to the given drain.

        @param drain: The drain to send flows to.

        @return: the next fount in the chain.
        """
        result = beginFlowingTo(self, drain)
        self._noDrainPause.maybeUnpause()
        for f, d in self._preListen:
            self._aFlowFunction(f, d)
        return result


    def pauseFlow(self):
        """
        Allow backpressure to build up in the listening socket; ask Twisted to
        stop calling C{accept}.

        @return: An L{IPause}.
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        Stop the delivery of L{Flow} objects to this L{_FountImpl}'s drain, and
        stop listening on the port represented by this fount.
        """
        self.drain.flowStopped(Failure(StopFlowCalled()))
        self.drain = None
        if IListeningPort.providedBy(self._portObject):
            self._portObject.stopListening()



def flowFountFromEndpoint(endpoint):
    """
    Listen on the given endpoint, and thereby create a L{fount <IFount>} which
    outputs a new L{Flow} for each connection.

    @note: L{IStreamServerEndpoint} formally specifies that its C{connect}
        method returns a L{Deferred} that fires with an L{IListeningPort}.
        However, L{IListeningPort} is insufficient to express the requisite
        flow-control to implement a fount; so the C{endpoint} parameter must be
        an extended endpoint whose C{listen} L{Deferred} fires with a provider
        of both L{IListeningPort} and L{IPushProducer}.  Luckily, the
        real-world implementations of L{IListeningPort} within Twisted are all
        L{IPushProducer}s as well, so practically speaking you will not notice
        this, but for testing it is important to know this is necessary.

    @param endpoint: a server endpoint.
    @type endpoint: L{IStreamServerEndpoint}

    @return: a L{twisted.internet.defer.Deferred} that fires with a L{IFount}
        whose C{outputType} is L{Flow}.
    """
    preListen = []
    def listening(portObject):
        listening.impl = _FountImpl(portObject, aFlowFunction, preListen)
        return listening.impl
    listening.impl = None
    def aFlowFunction(fount, drain):
        if listening.impl is None or listening.impl.drain is None:
            preListen.append((fount, drain))
            if listening.impl is not None:
                listening.impl._noDrainPause.pauseOnce()
        else:
            listening.impl.drain.receive(Flow(fount, drain))
    aFactory = _factoryFromFlow(aFlowFunction)
    return endpoint.listen(aFactory).addCallback(listening)



def flowFromEndpoint(endpoint):
    """
    Convert a client endpoint into a L{Deferred} that fires with a L{Flow}.

    @param endpoint: a client endpoint that will be connected to, once.

    @return: a L{Deferred} that fires with a L{Flow}.
    """
    def cb(fount, drain):
        cb.result = Flow(fount, drain)
    return (endpoint.connect(_factoryFromFlow(cb))
            .addCallback(lambda whatever: cb.result))
