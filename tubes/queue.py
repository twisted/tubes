# -*- test-case-name: tubes.test.test_queue -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The QueueFount.
"""

from collections import deque

from zope.interface import implementer
from twisted.internet import defer, task
from twisted.python.failure import Failure

from .kit import Pauser, beginFlowingTo
from .itube import IFount, StopFlowCalled


class NotABigTruckError(Exception):
    """
    A series of tubes is not just a big truck you
    can dump stuff onto...
    """
    pass



@implementer(IFount)
class QueueFount(object):
    """
    The queued fount. QueueFount can be used to apply flow backpressure.
    QueueFount's contract is to raise an exception if too many values are
    provided before the drain can consume them all.
    """
    drain = None
    flowIsPaused = False
    flowIsStopped = False
    flowIsStarted = False
    outputType = None

    def __init__(self, maxlen, clock):
        """
        Create an L{QueueFount} with a maximum queue length of C{maxLen}.
        """
        self._maxlen = maxlen
        self._clock = clock
        self._deque = deque(maxlen=self._maxlen)
        self._pauser = Pauser(self._actuallyPause, self._actuallyResume)
        self._turnDelay = 0
        self._lazyTail = defer.succeed(None)


    def flowTo(self, drain):
        """
        Start flowing to the given C{drain}.

        @param drain: the drain to deliver all inputs from this fount.

        @return: the fount downstream of C{drain}.
        """
        result = beginFlowingTo(self, drain)
        self.flowIsStarted = True
        self._turnDeque()
        return result


    def pauseFlow(self):
        """
        Pause the flow.

        @return: a pause
        @rtype: L{IPause}
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        End the flow and clear the deque.
        """
        self.flowIsStopped = True
        self._deque.clear()
        self.drain.flowStopped(Failure(StopFlowCalled()))


    def _actuallyPause(self):
        """
        Pause the flow (incrementing flowIsPaused).
        """
        self.flowIsPaused = True


    def _actuallyResume(self):
        """
        Resume the flow (decrementing flowIsPaused).
        """
        self.flowIsPaused = False
        self._turnDeque()


    def push(self, item):
        """
        Enqueue an item to be sent out our fount or
        raise an exception if our queue is full.

        @param item: any object
        """
        self._deque.append(item)
        if self.flowIsStarted and not self.flowIsPaused:
            self._clock.callLater(0, self._turnDeque)
        if len(self._deque) == self._maxlen:
            raise NotABigTruckError("QueueFount max queue length reached.")


    def _turnDeque(self):
        """
        Lazily process all the items in the queue
        unless we are paused or stopped.
        """
        if self.flowIsPaused or self.flowIsStopped:
            return
        try:
            item = self._deque.pop()
        except IndexError:
            self._lazyTail.addCallback(lambda ign: defer.succeed(None))
        else:
            self._lazyTail.addCallback(lambda ign: self.drain.receive(item))
            self._lazyTail.addCallback(
                lambda ign: task.deferLater(self._clock,
                                            self._turnDelay, self._turnDeque))
