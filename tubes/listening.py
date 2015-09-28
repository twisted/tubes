# -*- test-case-name: tubes.test.test_listening -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Listening.
"""

from zope.interface import implementer

from .itube import IDrain
from .kit import beginFlowingFrom, NoPause
from .tube import tube, series

class Flow(object):
    """
    A L{Flow} is a combination of a Fount and a Drain, representing a
    bi-directional communication channel such as a TCP connection.

    @ivar fount: A fount.

    @ivar drain: A drain.
    """

    def __init__(self, fount, drain):
        """
        @param fount: Fount.
        @type fount: L{IFount}

        @param drain: Drain.
        @type drain: L{IDrain}
        """
        self.fount = fount
        self.drain = drain



@implementer(IDrain)
class Listener(object):
    """
    A L{Listener} is a drain that accepts L{Flow}s and sets them up.
    """

    inputType = Flow

    def __init__(self, flowConnector, maxConnections=100):
        """
        @param flowConnector: a 1-argument callable taking a L{Flow} and
            returning nothing, which connects the flow.

        @param maxConnections: The number of concurrent L{Flow} objects
            to maintain active at once.
        @type maxConnections: L{int}
        """
        self.fount = None
        self._flowConnector = flowConnector
        self._maxConnections = maxConnections
        self._currentConnections = 0
        self._paused = NoPause()


    def flowingFrom(self, fount):
        """
        FIXME: DOCS

        @param fount: DOCS
        """
        beginFlowingFrom(self, fount)


    def receive(self, item):
        """
        Receive the given flow, applying backpressure if too many connections
        are active.

        @param item: The inbound L{Flow}.
        """
        self._currentConnections += 1
        if self._currentConnections >= self._maxConnections:
            self._paused = self.fount.pauseFlow()
        def dec():
            self._currentConnections -= 1
            self._paused.unpause()
            self._paused = NoPause()
        self._flowConnector(Flow(item.fount.flowTo(series(_OnStop(dec))),
                                 item.drain))


    def flowStopped(self, reason):
        """
        No more L{Flow}s are incoming; nothing to do.

        @param reason: the reason the flow stopped.
        """



@tube
class _OnStop(object):
    """
    Call a callback when the flow stops.
    """
    def __init__(self, callback):
        """
        Call the given callback.
        """
        self.callback = callback


    def received(self, item):
        """
        Pass through all received items.

        @param item: An item being passed through (type unknown).
        """
        yield item


    def stopped(self, reason):
        """
        Call the callback on stop.

        @param reason: the reason that the flow stopped; ignored.

        @return: no items.
        """
        self.callback()
        return ()
