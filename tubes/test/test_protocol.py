# -*- test-case-name: tubes.test.test_protocol -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.protocol}.
"""

from zope.interface import implementer

from twisted.trial.unittest import SynchronousTestCase as TestCase

from twisted.python.failure import Failure
from twisted.test.proto_helpers import StringTransport
from twisted.internet.interfaces import IStreamServerEndpoint

from ..protocol import flowFountFromEndpoint, flowFromEndpoint
from ..tube import tube, series
from ..listening import Flow, Listener
from ..itube import IFount

from .util import StringEndpoint, FakeDrain, FakeFount, fakeEndpointWithPorts

@tube
class RememberingTube(object):
    """
    A tube that remembers what it receives.

    @ivar items: a list of objects that have been received.
    """

    def __init__(self):
        self.items = []
        self.wasStopped = False
        self.started()


    def received(self, item):
        """
        Remember the given item in C{items} and and yield nothing.

        @param item: The item to remember.
        """
        self.items.append(item)


    def stopped(self, reason):
        """
        Remember that the flow was stopped in the C{wasStopped} attribute and
        the reason for it in the C{reason} attribute, respectively.

        @param reason: the reason the flow stopped.
        """
        self.wasStopped = True
        self.reason = reason



class FlowConnectorTests(TestCase):
    """
    Tests for L{flowFromEndpoint} and the drain/fount/factory adapters it
    constructs.
    """

    def setUp(self):
        """
        Sert up these tests.
        """
        self.endpoint = StringEndpoint()
        flow = self.successResultOf(flowFromEndpoint(self.endpoint))
        self.adaptedDrain = flow.drain
        self.adaptedFount = flow.fount
        self.tube = RememberingTube()
        self.drain = series(self.tube)


    def adaptedProtocol(self):
        """
        Retrieve a protocol for testing with.

        @return: the first protocol instance to have been created by making the
            virtual outbound connection associated with the call to
            L{flowFromEndpoint} performed in L{FlowConnectorTests.setUp}.
        @rtype: L{IProtocol}
        """
        return self.endpoint.transports[0].protocol


    def test_flowToSetsDrain(self):
        """
        L{_TransportFount.flowTo} will set the C{drain} attribute of the
        L{_TransportFount}.
        """
        self.adaptedFount.flowTo(self.drain)
        self.assertIdentical(self.adaptedFount.drain, self.drain)


    def test_flowToDeliversData(self):
        """
        L{_TransportFount.flowTo} will cause subsequent calls to
        L{_ProtocolPlumbing.dataReceived} to invoke L{receive} on its drain.
        """
        self.adaptedFount.flowTo(self.drain)
        self.adaptedProtocol().dataReceived("some data")
        self.assertEqual(self.tube.items, ["some data"])


    def test_drainReceivingWritesToTransport(self):
        """
        Calling L{receive} on a L{_TransportDrain} will send the data to the
        wrapped transport.
        """
        hello = b"hello world!"
        self.adaptedDrain.receive(hello)
        self.assertEqual(self.endpoint.transports[0].io.getvalue(), hello)


    def test_stopFlowStopsConnection(self):
        """
        L{_TransportFount.stopFlow} will close the underlying connection by
        calling C{loseConnection} on it.
        """
        self.adaptedFount.flowTo(self.drain)
        self.adaptedFount.stopFlow()
        self.assertEqual(self.adaptedProtocol().transport.disconnecting, True)
        # The connection has not been closed yet; we *asked* the flow to stop,
        # but it may not have done.
        self.assertEqual(self.tube.wasStopped, False)


    def test_flowStoppedStopsConnection(self):
        """
        L{_TransportDrain.flowStopped} will close the underlying connection by
        calling C{loseConnection} on it.
        """
        self.adaptedFount.flowTo(self.drain)
        self.adaptedDrain.flowStopped(Failure(ZeroDivisionError()))
        self.assertEqual(self.adaptedProtocol().transport.disconnecting, True)
        self.assertEqual(self.tube.wasStopped, False)


    def test_connectionLostSendsFlowStopped(self):
        """
        When C{connectionLost} is called on a L{_ProtocolPlumbing} and it has
        an L{IFount} flowing to it (in other words, flowing to its
        L{_TransportDrain}), but no drain flowing I{from} it, the L{IFount}
        should have C{stopFlow} invoked on it so that it will no longer deliver
        to the now-dead transport.
        """
        self.adaptedFount.flowTo(self.drain)
        class MyFunException(Exception):
            pass
        f = Failure(MyFunException())
        self.adaptedProtocol().connectionLost(f)
        self.assertEqual(self.tube.wasStopped, True)
        self.assertIdentical(f, self.tube.reason)


    def test_connectionLostSendsStopFlow(self):
        """
        L{_ProtocolPlumbing.connectionLost} will notify its C{_drain}'s
        C{fount} that it should stop flowing, since the connection is now gone.
        """
        ff = FakeFount()
        ff.flowTo(self.adaptedDrain)
        self.assertEqual(ff.flowIsStopped, False)
        self.adaptedProtocol().connectionLost(Failure(ZeroDivisionError()))
        self.assertEqual(ff.flowIsStopped, True)


    def test_dataReceivedBeforeFlowing(self):
        """
        If L{_ProtocolPlumbing.dataReceived} is called before its
        L{_TransportFount} is flowing to anything, then it will pause the
        transport but only until the L{_TransportFount} is flowing to
        something.
        """
        self.adaptedProtocol().dataReceived("hello, ")
        self.assertEqual(self.adaptedProtocol().transport.producerState,
                          'paused')
        # It would be invalid to call dataReceived again in this state, so no
        # need to test that...
        fd = FakeDrain()
        self.adaptedFount.flowTo(fd)
        self.assertEqual(self.adaptedProtocol().transport.producerState,
                         'producing')
        self.adaptedProtocol().dataReceived("world!")
        self.assertEqual(fd.received, ["hello, ", "world!"])


    def test_dataReceivedBeforeFlowingThenFlowTo(self):
        """
        Repeated calls to L{flowTo} don't replay the buffer from
        L{dataReceived} to the new drain.
        """
        self.test_dataReceivedBeforeFlowing()
        fd2 = FakeDrain()
        self.adaptedFount.flowTo(fd2)
        self.adaptedProtocol().dataReceived("hooray")
        self.assertEqual(fd2.received, ["hooray"])


    def test_dataReceivedWhenFlowingToNone(self):
        """
        Initially flowing to L{None} is the same as flowTo never having been
        called, so L{_ProtocolPlumbing.dataReceived} should have the same
        effect.
        """
        self.adaptedFount.flowTo(None)
        self.test_dataReceivedBeforeFlowing()


    def test_flowingToNoneAfterFlowingToSomething(self):
        """
        Flowing to L{None} should disconnect from any drain, no longer
        delivering it output.
        """
        fd = FakeDrain()
        self.adaptedFount.flowTo(fd)
        self.adaptedProtocol().dataReceived("a")
        self.adaptedFount.flowTo(None)
        self.assertEqual(fd.fount, None)
        self.test_dataReceivedBeforeFlowing()
        self.assertEqual(fd.received, ["a"])


    def test_flowingFromAttribute(self):
        """
        L{_TransportDrain.flowingFrom} will establish the appropriate L{IFount}
        to deliver L{pauseFlow} notifications to.
        """
        ff = FakeFount()
        self.adaptedDrain.flowingFrom(ff)
        self.assertIdentical(self.adaptedDrain.fount, ff)


    def test_pauseUnpauseFromTransport(self):
        """
        When an L{IFount} produces too much data for a L{_TransportDrain} to
        process, the L{push producer
        <twisted.internet.interfaces.IPushProducer>} associated with the
        L{_TransportDrain}'s transport will relay the L{pauseProducing}
        notification to that L{IFount}'s C{pauseFlow} method.
        """
        ff = FakeFount()
        # Sanity check.
        self.assertEqual(ff.flowIsPaused, False)
        self.adaptedDrain.flowingFrom(ff)
        # The connection is too full!  Back off!
        self.adaptedProtocol().transport.producer.pauseProducing()
        self.assertEqual(ff.flowIsPaused, True)
        # All clear, start writing again.
        self.adaptedProtocol().transport.producer.resumeProducing()
        self.assertEqual(ff.flowIsPaused, False)


    def test_pauseUnpauseFromOtherDrain(self):
        """
        When a L{_TransportFount} produces too much data for a L{drain
        <IDrain>} to process, and it calls L{_TransportFount.pauseFlow}, the
        underlying transport will be paused.
        """
        fd = FakeDrain()
        # StringTransport is an OK API.  But it is not the _best_ API.
        producing = 'producing'
        paused = 'paused'
        # Sanity check.
        self.assertEqual(self.adaptedProtocol().transport.producerState,
                         producing)
        self.adaptedFount.flowTo(fd)
        # Steady as she goes.
        self.assertEqual(self.adaptedProtocol().transport.producerState,
                         producing)
        anPause = fd.fount.pauseFlow()
        self.assertEqual(self.adaptedProtocol().transport.producerState,
                         paused)
        anPause.unpause()
        self.assertEqual(self.adaptedProtocol().transport.producerState,
                         producing)


    def test_stopProducing(self):
        """
        When C{stopProducing} is called on the L{push producer
        <twisted.internet.interfaces.IPushProducer>} associated with the
        L{_TransportDrain}'s transport, the L{_TransportDrain}'s C{fount}'s
        C{stopFlow} method will be invoked.
        """
        ff = FakeFount()
        ff.flowTo(self.adaptedDrain)
        self.adaptedDrain._transport.producer.stopProducing()
        self.assertEqual(ff.flowIsStopped, True)


    def test_flowingFrom(self):
        """
        L{_TransportFount.flowTo} returns the result of its argument's
        C{flowingFrom}.
        """
        another = FakeFount()
        class ReflowingFakeDrain(FakeDrain):
            def flowingFrom(self, fount):
                super(ReflowingFakeDrain, self).flowingFrom(fount)
                return another
        anotherOther = self.adaptedFount.flowTo(ReflowingFakeDrain())
        self.assertIdentical(another, anotherOther)


    def test_flowingFromTwice(self):
        """
        L{_TransportDrain.flowingFrom} switches the producer registered with
        the underlying transport.
        """
        upstream1 = FakeFount()
        upstream2 = FakeFount()

        upstream1.flowTo(self.adaptedDrain)
        upstream2.flowTo(self.adaptedDrain)

        self.assertEqual(self.adaptedDrain._transport.producer._fount,
                         upstream2)



class FlowListenerTests(TestCase):
    """
    Tests for L{flowFountFromEndpoint} and the fount adapter it constructs.
    """

    def test_fromEndpoint(self):
        """
        L{flowFountFromEndpoint} returns a L{Deferred} that fires when the
        listening port is ready.
        """
        endpoint, ports = fakeEndpointWithPorts()
        deferred = flowFountFromEndpoint(endpoint)
        self.assertNoResult(deferred)
        deferred.callback(None)
        result = self.successResultOf(deferred)
        self.assertTrue(IFount.providedBy(result))
        self.assertEqual(result.outputType.implementedBy(Flow), True)


    def test_oneConnectionAccepted(self):
        """
        When a connection comes in to a listening L{flowFountFromEndpoint}, the
        L{Listener} that it's flowing to's callback is called.
        """
        endpoint, ports = fakeEndpointWithPorts()
        deferred = flowFountFromEndpoint(endpoint)
        self.assertNoResult(deferred)
        deferred.callback(None)
        result = self.successResultOf(deferred)
        connected = []
        result.flowTo(Listener(connected.append))
        protocol = ports[0].factory.buildProtocol(None)
        self.assertEqual(len(connected), 0)
        protocol.makeConnection(StringTransport())
        self.assertEqual(len(connected), 1)


    def test_acceptBeforeActuallyListening(self):
        """
        Sometimes a connection is established reentrantly by C{listen}, without
        waiting for the L{Deferred} returned to fire.  In this case the
        connection will be buffered until said L{Deferred} fires.
        """
        immediateTransport = StringTransport()
        subEndpoint, ports = fakeEndpointWithPorts()
        @implementer(IStreamServerEndpoint)
        class ImmediateFakeEndpoint(object):
            def listen(self, factory):
                protocol = factory.buildProtocol(None)
                protocol.makeConnection(immediateTransport)
                return subEndpoint.listen(factory)
        endpoint = ImmediateFakeEndpoint()
        deferred = flowFountFromEndpoint(endpoint)
        deferred.callback(None)
        fount = self.successResultOf(deferred)
        connected = []
        self.assertEqual(ports[0].currentlyProducing, False)
        fount.flowTo(Listener(connected.append))
        self.assertEqual(ports[0].currentlyProducing, True)
        self.assertEqual(len(connected), 1)


    def test_acceptAfterDeferredButBeforeFlowTo(self):
        """
        If the L{Deferred} returned by L{flowFountFromEndpoint} fires, but the
        callback doesn't immediately call C{flowTo} on the result, the
        listening port will be paused.
        """
        endpoint, ports = fakeEndpointWithPorts()
        fffed = flowFountFromEndpoint(endpoint)
        fffed.callback(None)
        flowFount = self.successResultOf(fffed)
        self.assertEqual(ports[0].currentlyProducing, True)
        protocol = ports[0].factory.buildProtocol(None)
        aTransport = StringTransport()
        protocol.makeConnection(aTransport)
        self.assertEqual(ports[0].currentlyProducing, False)
        fd = FakeDrain()
        flowFount.flowTo(fd)
        self.assertEqual(ports[0].currentlyProducing, True)


    def test_backpressure(self):
        """
        When the L{IFount} returned by L{flowFountFromEndpoint} is paused, it
        removes its listening port from the reactor.  When resumed, it re-adds
        it.
        """
        endpoint, ports = fakeEndpointWithPorts()
        deferred = flowFountFromEndpoint(endpoint)
        deferred.callback(None)
        fount = self.successResultOf(deferred)
        fount.flowTo(FakeDrain())
        pause = fount.pauseFlow()
        self.assertEqual(ports[0].currentlyProducing, False)
        pause.unpause()
        self.assertEqual(ports[0].currentlyProducing, True)


    def test_stopping(self):
        """
        The L{IFount} returned by L{flowFountFromEndpoint} will stop listening
        on the endpoint
        """
        endpoint, ports = fakeEndpointWithPorts()
        deferred = flowFountFromEndpoint(endpoint)
        deferred.callback(None)
        fount = self.successResultOf(deferred)
        fd = FakeDrain()
        fount.flowTo(fd)
        fount.stopFlow()
        self.assertEqual(ports[0].listenStopping, True)
        self.assertEqual(len(fd.stopped), 1)
