# -*- test-case-name: tubes.test.test_queue -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from collections import deque

from zope.interface import implementer
from twisted.internet import defer, task

from .kit import Pauser, beginFlowingTo
from .itube import IFount


@implementer(IFount)
class QueueFount(object):
    """
    The queue fount.
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
        self._pauser = Pauser(self._actuallyPause, self._actuallyResume)
        self._deque = deque(maxlen=self._maxlen)
        self._turn_delay = 0
        self._lazy_tail = defer.succeed(None)
        
    def flowTo(self, drain):
        """
        Start flowing to the given C{drain}.

        @param drain: the drain to deliver all inputs from this fount.

        @return: the fount downstream of C{drain}.
        """
        result = beginFlowingTo(self, drain)
        self.flowIsStarted = True
        self._turn_deque()
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
        self.drain.flowStopped()

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
            self._turn_deque()

    def push(self, item):
        """
        Enqueue an item to be sent out our fount.
        """
        self._deque.append(item)
        if self.flowIsStarted and self.flowIsPaused == 0:
            self._clock.callLater(0, self._turn_deque)

    def _turn_deque(self):
        if self.flowIsPaused > 0 or self.flowIsStopped:
            return
        try:
            item = self._deque.pop()
        except IndexError:
            self._lazy_tail.addCallback(lambda ign: defer.succeed(None))
        else:
            self._lazy_tail.addCallback(lambda ign: self.drain.receive(item))
            self._lazy_tail.addCallback(lambda ign: task.deferLater(self._clock, self._turn_delay, self._turn_deque))
