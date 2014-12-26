
from twisted.trial.unittest import SynchronousTestCase

from zope.interface.verify import verifyObject

from ..memory import IteratorFount

from ..itube import IFount, StopFlowCalled

from .util import FakeDrain, FakeFount

class DrainThatStops(FakeDrain):
    # TODO: possibly promote to util
    def receive(self, item):
        super(DrainThatStops, self).receive(item)
        self.fount.stopFlow()

class DrainThatPauses(FakeDrain):
    # TODO: possibly promote to util
    def receive(self, item):
        super(DrainThatPauses, self).receive(item)
        self.pause = self.fount.pauseFlow()

class IteratorFountTests(SynchronousTestCase):
    """
    Tests for L{tubes.memory.IteratorFount}.
    """

    def test_flowTo(self):
        """
        L{IteratorFount.flowTo} sets its drain and calls C{flowingFrom} on its
        argument, returning that value.
        """
        f = IteratorFount([])
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
        L{IteratorFount.flowTo} will deliver all of its values to the given
        drain.
        """
        f = IteratorFount([1, 2, 3])
        fd = FakeDrain()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1, 2, 3])


    def test_pauseFlow(self):
        """
        L{IteratorFount.pauseFlow} will pause the delivery of items.
        """
        f = IteratorFount([1, 2, 3])
        fd = DrainThatPauses()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1])


    def test_unpauseFlow(self):
        """
        When all pauses returned by L{IteratorFount.pauseFlow} have been
        unpaused, the flow resumes.
        """
        f = IteratorFount([1, 2, 3])
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
        L{IteratorFount.stopFlow} stops the flow, propagating a C{flowStopped}
        call to its drain and ceasing delivery immediately.
        """
        f = IteratorFount([1, 2, 3])

        fd = DrainThatStops()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1])
        self.assertEqual(fd.stopped[0].type, StopFlowCalled)


    def test_stopIterationStopsIteration(self):
        """
        When the iterator passed to L{IteratorFount} is exhausted
        L{IDrain.flowStopped} is called with L{StopIteration} as it's
        reason.
        """
        f = IteratorFount([1, 2, 3])
        fd = FakeDrain()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1, 2, 3])
        self.assertEqual(fd.stopped[0].type, StopIteration)


    def test_stopFlowCalledAfterFlowStopped(self):
        """
        L{IteratorFount} will only call its C{drain}'s L{flowStopped} once when
        C{stopFlow} is called after the flow has stopped due to iterator
        exhaustion.
        """
        f = IteratorFount([1])
        fd = FakeDrain()
        f.flowTo(fd)
        self.assertEqual(fd.received, [1])
        self.assertEqual(len(fd.stopped), 1)
        f.stopFlow()
        self.assertEqual(len(fd.stopped), 1)
        self.assertEqual(fd.stopped[0].type, StopIteration)


    def test_stopPausedFlow(self):
        """
        When L{IteratorFount} is stopped after being paused, the drain will
        receive a C{flowStopped} when it is resumed.
        """
        f = IteratorFount([1, 2])
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
        When L{IteratorFount} is stopped after being paused, and subsequently
        unpaused it should not start flowing again.
        """
        f = IteratorFount([1, 2])
        fd = DrainThatPauses()
        f.flowTo(fd)
        f.stopFlow()
        fd.pause.unpause()
        self.assertEqual(fd.received, [1])


    def test_provides(self):
        """
        An L{IteratorFount} provides L{IFount}.
        """
        verifyObject(IFount, IteratorFount([]))
