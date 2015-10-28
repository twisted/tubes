
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
        qFount.push("something")
        qFount.push("something")
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["something", "something"])

    def test_push_before_drained(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        qFount.push("something")
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["something"])

    def test_max_len(self):
        testClock = task.Clock()
        maxlen = 2
        qFount = QueueFount(maxlen, testClock)
        qFount.push("something")
        qFount.push("something")
        self.assertEqual(maxlen, qFount._deque_len)
        self.assertRaises(NotABigTruckError, qFount.push, "something")
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["something", "something"])

    def test_push_while_paused(self):
        testClock = task.Clock()
        maxlen = 2
        qFount = QueueFount(maxlen, testClock)
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        pauser = qFount.pauseFlow()
        qFount.push("something")
        self.assertEqual(1, qFount._deque_len)
        self.assertEqual(qFount.flowIsPaused, 1)
        self.assertEqual(list(qFount._deque), ["something"])
        self.assertEqual(qFount._deque_len, 1)
        pauser.unpause()
        self.assertEqual(qFount.flowIsPaused, 0)
        testClock.advance(0)
        self.assertEqual(aFakeDrain.received, ["something"])

    def test_stop_before_sent(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        qFount.push("something")
        qFount.stopFlow()
        testClock.advance(0)
        self.assertTrue(qFount.flowIsStopped)
        self.assertEqual(len(list(qFount._deque)), 0)
        self.assertEqual(qFount._deque_len, 0)
        self.assertEqual(aFakeDrain.received, [])

    def test_stop_after_sent(self):
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        aFakeDrain = FakeDrain()
        result = qFount.flowTo(aFakeDrain)
        qFount.push("something")
        testClock.advance(0)
        qFount.stopFlow()
        self.assertTrue(qFount.flowIsStopped)
        self.assertEqual(len(list(qFount._deque)), 0)
        self.assertEqual(qFount._deque_len, 0)
        self.assertEqual(aFakeDrain.received, ["something"])
