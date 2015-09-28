
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
        
        """
        return beginFlowingFrom(self, fount)


    def receive(self, item):
        """
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
        """


@tube
class _OnStop(object):
    def __init__(self, callback):
        self.callback = callback


    def received(self, item):
        yield item


    def stopped(self, reason):
        self.callback()
        return ()
