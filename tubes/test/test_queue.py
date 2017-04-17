# -*- test-case-name: tubes.test.test_queue -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.queue}.
"""

from twisted.trial.unittest import SynchronousTestCase
from twisted.internet import task

from ..test.util import FakeDrain
from ..queue import QueueFount, NotABigTruckError


class QueueFountTests(SynchronousTestCase):
    """
    Tests for L{tubes.queue.QueueFount}
    """
    def test_basic(self):
        """
        Test that L{QueueFount} queues and then sends
        a couple of items to it's attached drain.
        """
        testClock = task.Clock()
        qFount = QueueFount(10, testClock)
        aFakeDrain = FakeDrain()
        qFount.flowTo(aFakeDrain)
        qFount.push("something")
        qFount.push("something")
        qFount.push(42)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, [42, "something", "something"])


    def test_push_before_drained(self):
        """
        Test that we can queue data before
        attaching a drain.
        """
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        qFount.push("something")
        aFakeDrain = FakeDrain()
        qFount.flowTo(aFakeDrain)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, ["something"])


    def test_max_len(self):
        """
        Test that we throw the proper exception upon reaching
        maximum length of our deque.
        """
        testClock = task.Clock()
        maxlen = 2
        qFount = QueueFount(maxlen, testClock)
        qFount.push("oldest")
        self.assertRaises(NotABigTruckError, qFount.push, 2)
        self.assertEqual(maxlen, len(qFount._deque))
        self.assertRaises(NotABigTruckError, qFount.push, {'3': 3})
        aFakeDrain = FakeDrain()
        qFount.flowTo(aFakeDrain)
        testClock.advance(0)
        self.assertEquals(aFakeDrain.received, [{'3': 3}, 2])


    def test_push_while_paused(self):
        """
        Test that we can push to the queue while it's flow
        is paused... and then upon resume we send the item.
        """
        testClock = task.Clock()
        maxlen = 2
        qFount = QueueFount(maxlen, testClock)
        aFakeDrain = FakeDrain()
        qFount.flowTo(aFakeDrain)
        pauser = qFount.pauseFlow()
        qFount.push("something")
        self.assertEqual(1, len(qFount._deque))
        self.assertEqual(qFount.flowIsPaused, 1)
        self.assertEqual(list(qFount._deque), ["something"])
        pauser.unpause()
        self.assertEqual(qFount.flowIsPaused, 0)
        testClock.advance(0)
        self.assertEqual(aFakeDrain.received, ["something"])


    def test_stop_before_sent(self):
        """
        Test that if we stop before the queue
        is drain that we empty the queue.
        """
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        aFakeDrain = FakeDrain()
        qFount.flowTo(aFakeDrain)
        qFount.push("something")
        qFount.stopFlow()
        testClock.advance(0)
        self.assertTrue(qFount.flowIsStopped)
        self.assertEqual(len(qFount._deque), 0)
        self.assertEqual(aFakeDrain.received, [])


    def test_stop_after_sent(self):
        """
        Test that stop works correctly
        after draining our queue.
        """
        testClock = task.Clock()
        qFount = QueueFount(2, testClock)
        aFakeDrain = FakeDrain()
        qFount.flowTo(aFakeDrain)
        qFount.push("something")
        testClock.advance(0)
        qFount.stopFlow()
        self.assertTrue(qFount.flowIsStopped)
        self.assertEqual(len(qFount._deque), 0)
        self.assertEqual(aFakeDrain.received, ["something"])
