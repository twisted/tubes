
from twisted.trial.unittest import SynchronousTestCase
from twisted.internet import reactor, task, defer

from ..itube import IFount, IDrain, StopFlowCalled
from ..test.util import FakeFount, FakeDrain
from ..queue import QueueFount, NotABigTruckError


class QueueFountTests(SynchronousTestCase):

    def test_basic(self):
        testClock = task.Clock()
        qFount = QueueFount(10, testClock)
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        qFount.push("meow")
        qFount.push("meow")
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["meow", "meow"])

    def test_push_before_drained(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        qFount.push("meow")
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["meow"])

    def test_max_len(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        qFount.push("meow")
        qFount.push("meow")
        self.assertRaises(NotABigTruckError, qFount.push, "meow")
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["meow", "meow"])

    def test_push_while_paused(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        pauser = qFount.pauseFlow()
        qFount.push("something")
        self.assertEqual(qFount.flowIsPaused, 1)
        pauser.unpause()
        self.assertEqual(qFount.flowIsPaused, 0)
        testClock.advance(0)
        self.assertEqual(aFakeDrain.received, ["something"])

    def test_stop_flow(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        qFount.push("something")
        qFount.stopFlow()
        testClock.advance(0)
        self.assertTrue(qFount.flowIsStopped)
        self.assertEqual(len(list(qFount._deque)), 0)
