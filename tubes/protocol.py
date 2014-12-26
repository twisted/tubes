# -*- test-case-name: tubes.test.test_protocol -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Objects to connect L{real data <twisted.internet.protocol.Protocol>} to
L{Tube}s.

@see: L{factoryFromFlow}
"""

__all__ = [
    'factoryFromFlow',
]

from zope.interface import implementer

from .kit import Pauser, beginFlowingFrom, beginFlowingTo
from .itube import IDrain, IFount, ISegment

from twisted.internet.interfaces import IPushProducer
from twisted.internet.protocol import Protocol as _Protocol


@implementer(IPushProducer)
class _FountProducer(object):
    """
    A L{_FountProducer} is an adapter to L{IPushProducer} for an L{IFount}.

    @ivar _fount: An L{IFount}.
    @type _fount: L{IFount}.

    @ivar _pause: A pause if the fount has been paused by C{pauseProducing}
    @type _pause: L{IPause} or L{NoneType}
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
        """
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
    @type _preReceivePause: L{IPause} or L{NoneType}

    @ivar _preReceiveBuffer: If data is received from the protocol when no
        drain is connected, then this will be the bytes.
    @type _preReceiveBuffer: L{bytes} or L{NoneType}
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

    @ivar _flow: A flow function, as described in L{factoryFromFlow}.
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



def factoryFromFlow(flow):
    """
    Convert a flow function into an L{IProtocolFactory}.

    A "flow function" is a function which takes a L{fount <IFount>} and an
    L{drain <IDrain>}.

    L{factoryFromFlow} takes such a function and creates an L{IProtocolFactory}
    which, upon each new connection, provides the flow function with an
    L{IFount} and an L{IDrain} representing the read end and the write end of
    the incoming connection, respectively.

    @param flow: a 2-argument callable, taking (fount, drain).
    @type flow: L{callable}

    @return: a protocol factory.
    @rtype: L{IProtocolFactory}
    """
    from twisted.internet.protocol import Factory
    return Factory.forProtocol(lambda: _ProtocolPlumbing(flow))
