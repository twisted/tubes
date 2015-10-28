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
    flowIsPaused = 0
    flowIsStopped = False
    flowIsStarted = False
    outputType = None # XXX needed?

    def __init__(self, maxlen, clock):
        """
        Create an L{QueueFount} with a maximum queue length of C{maxLen}.
        """
        self._maxlen = maxlen
        self._clock = clock
        self._deque = deque(maxlen=self._maxlen)
        self._dequeLen = 0
        self._pauser = Pauser(self._actuallyPause, self._actuallyResume)
        self._turnDelay = 0
        self._lazy_tail = defer.succeed(None)


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
        self._dequeLen = 0
        self._deque.clear()
        self.drain.flowStopped(Failure(StopFlowCalled()))


    def _actuallyPause(self):
        """
        Pause the flow (incrementing flowIsPaused).
        """
        self.flowIsPaused += 1


    def _actuallyResume(self):
        """
        Resume the flow (decrementing flowIsPaused).
        """
        self.flowIsPaused -= 1
        if self.flowIsPaused == 0:
            self._turnDeque()


    def push(self, item):
        """
        Enqueue an item to be sent out our fount or
        raise an exception with our queue is full.
        """
        self._dequeLen += 1
        self._deque.append(item)
        if self.flowIsStarted and self.flowIsPaused == 0:
            self._clock.callLater(0, self._turnDeque)
        if self._dequeLen > self._maxlen:
            raise NotABigTruckError("QueueFount max queue length reached.")


    def _turnDeque(self):
        """Lazily process all the items in the queue
        unless we are paused or stopped.
        """
        if self.flowIsPaused > 0 or self.flowIsStopped:
            return
        try:
            item = self._deque.pop()
        except IndexError:
            self._lazy_tail.addCallback(lambda ign: defer.succeed(None))
        else:
            self._dequeLen -= 1
            self._lazy_tail.addCallback(lambda ign: self.drain.receive(item))
            self._lazy_tail.addCallback(lambda ign: task.deferLater(self._clock,
                                                                    self._turnDelay, self._turnDeque))
