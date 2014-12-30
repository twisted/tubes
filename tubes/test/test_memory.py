# -*- test-case-name: tubes.test.test_memory -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.memory}.
"""

from twisted.trial.unittest import SynchronousTestCase

from zope.interface.verify import verifyObject

from ..memory import iteratorFount

from ..itube import IFount, StopFlowCalled

from .util import FakeDrain, FakeFount

class DrainThatStops(FakeDrain):
    """
    Drain that stops its fount upon receive.
    """
    # TODO: possibly promote to util
    def receive(self, item):
        """
        Receive one item and stop.

        @param item: any object.
        """
        super(DrainThatStops, self).receive(item)
        self.fount.stopFlow()



class DrainThatPauses(FakeDrain):
    """
    Drain that pauses its fount upon receive.
    """
    # TODO: possibly promote to util
    def receive(self, item):
        """
        Receive one item and pause.

        @param item: any object.
        """
        super(DrainThatPauses, self).receive(item)
        self.pause = self.fount.pauseFlow()



class IteratorFountTests(SynchronousTestCase):
    """
    Tests for L{tubes.memory.iteratorFount}.
    """

    def test_flowTo(self):
        """
        L{iteratorFount.flowTo} sets its drain and calls C{flowingFrom} on its
        argument, returning that value.
        """
        f = iteratorFount([])
        ff = FakeFount()
        class FakeDrainThatContinues(FakeDrain):
            def flowingFrom(self, fount):
                super(FakeDrainThatContinues, self).flowingFrom(fount)
                return ff
        fd = FakeDrainThatContinues()
        result = f.flowTo(fd)

        self.assertIdentical(fd.fount, f)
        self.assertIdentical(f.drain, fd)
        self.assertIdentical(result, ff)


    def test_flowToDeliversValues(self):
        """
        L{iteratorFount.flowTo} will deliver all of its values to the given
        drain.
        """
        f = iteratorFount([1, 2, 3])
        fd = FakeDrain()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1, 2, 3])


    def test_pauseFlow(self):
        """
        L{iteratorFount.pauseFlow} will pause the delivery of items.
        """
        f = iteratorFount([1, 2, 3])
        fd = DrainThatPauses()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1])


    def test_unpauseFlow(self):
        """
        When all pauses returned by L{iteratorFount.pauseFlow} have been
        unpaused, the flow resumes.
        """
        f = iteratorFount([1, 2, 3])
        fd = FakeDrain()
        pauses = [f.pauseFlow(), f.pauseFlow()]
        f.flowTo(fd)
        self.assertEqual(fd.received, [])
        pauses.pop().unpause()
        self.assertEqual(fd.received, [])
        pauses.pop().unpause()
        self.assertEqual(fd.received, [1, 2, 3])


    def test_stopFlow(self):
        """
        L{iteratorFount.stopFlow} stops the flow, propagating a C{flowStopped}
        call to its drain and ceasing delivery immediately.
        """
        f = iteratorFount([1, 2, 3])

        fd = DrainThatStops()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1])
        self.assertEqual(fd.stopped[0].type, StopFlowCalled)


    def test_stopIterationStopsIteration(self):
        """
        When the iterator passed to L{iteratorFount} is exhausted
        L{IDrain.flowStopped} is called with L{StopIteration} as it's
        reason.
        """
        f = iteratorFount([1, 2, 3])
        fd = FakeDrain()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1, 2, 3])
        self.assertEqual(fd.stopped[0].type, StopIteration)


    def test_stopFlowCalledAfterFlowStopped(self):
        """
        L{iteratorFount} will only call its C{drain}'s L{flowStopped} once when
        C{stopFlow} is called after the flow has stopped due to iterator
        exhaustion.
        """
        f = iteratorFount([1])
        fd = FakeDrain()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1])
        self.assertEqual(len(fd.stopped), 1)
        f.stopFlow()
        self.assertEqual(len(fd.stopped), 1)
        self.assertEqual(fd.stopped[0].type, StopIteration)


    def test_stopPausedFlow(self):
        """
        When L{iteratorFount} is stopped after being paused, the drain will
        receive a C{flowStopped} when it is resumed.
        """
        f = iteratorFount([1, 2])
        fd = DrainThatPauses()
        f.flowTo(fd)
        f.stopFlow()
        self.assertEqual(fd.received, [1])
        self.assertEqual(len(fd.stopped), 0)
        fd.pause.unpause()
        self.assertEqual(len(fd.stopped), 1)
        self.assertEqual(fd.stopped[0].type, StopFlowCalled)


    def test_flowUnpausedAfterPausedFlowIsStopped(self):
        """
        When L{iteratorFount} is stopped after being paused, and subsequently
        unpaused it should not start flowing again.
        """
        f = iteratorFount([1, 2])
        fd = DrainThatPauses()
        f.flowTo(fd)
        f.stopFlow()
        fd.pause.unpause()
        self.assertEqual(fd.received, [1])


    def test_provides(self):
        """
        An L{iteratorFount} provides L{IFount}.
        """
        verifyObject(IFount, iteratorFount([]))
