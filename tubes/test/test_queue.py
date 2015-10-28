
from twisted.trial.unittest import SynchronousTestCase
from twisted.internet import reactor, task, defer

from ..itube import IFount, IDrain
from ..test.util import FakeFount, FakeDrain
from ..queue import QueueFount, NotABigTruckError

import time

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

    def test_pause_resume(self):
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
