# -*- test-case-name: tubes.test.test_undefer -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.undefer}.
"""

from twisted.trial.unittest import SynchronousTestCase
from twisted.internet.defer import succeed
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from tubes.undefer import deferredToResult, fountToDeferred
from tubes.test.util import FakeDrain
from tubes.test.util import FakeFount
from tubes.tube import tube, series

class DeferredIntegrationTests(SynchronousTestCase):
    """
    Tests for L{deferredToResult}.
    """
    def setUp(self):
        """
        Create a fount and drain.
        """
        self.ff = FakeFount()
        self.fd = FakeDrain()


    def test_tubeYieldsFiredDeferred(self):
        """
        When a tube yields a fired L{Deferred} its result is synchronously
        delivered.
        """

        @tube
        class SucceedingTube(object):
            def received(self, data):
                yield succeed(''.join(reversed(data)))

        fakeDrain = self.fd
        self.ff.flowTo(series(SucceedingTube(),
                              deferredToResult())).flowTo(fakeDrain)
        self.ff.drain.receive("hello")
        self.assertEquals(self.fd.received, ["olleh"])


    def test_tubeYieldsUnfiredDeferred(self):
        """
        When a tube yields an unfired L{Deferred} its result is asynchronously
        delivered.
        """

        d = Deferred()

        @tube
        class WaitingTube(object):
            def received(self, data):
                yield d

        fakeDrain = self.fd
        self.ff.flowTo(series(WaitingTube(),
                              deferredToResult())).flowTo(fakeDrain)
        self.ff.drain.receive("ignored")
        self.assertEquals(self.fd.received, [])

        d.callback("hello")

        self.assertEquals(self.fd.received, ["hello"])


    def test_tubeYieldsMultipleDeferreds(self):
        """
        When a tube yields multiple deferreds their results should be delivered
        in order.
        """

        d = Deferred()

        @tube
        class MultiDeferredTube(object):
            didYield = False
            def received(self, data):
                yield d
                MultiDeferredTube.didYield = True
                yield succeed("goodbye")

        fakeDrain = self.fd
        self.ff.flowTo(series(MultiDeferredTube(),
                              deferredToResult())).flowTo(fakeDrain)
        self.ff.drain.receive("ignored")
        self.assertEquals(self.fd.received, [])

        d.callback("hello")

        self.assertEquals(self.fd.received, ["hello", "goodbye"])


    def test_tubeYieldedDeferredFiresWhileFlowIsPaused(self):
        """
        When a L{Tube} yields an L{Deferred} and that L{Deferred} fires when
        the L{_SiphonFount} is paused it should buffer it's result and deliver
        it when L{_SiphonFount.resumeFlow} is called.
        """
        d = Deferred()

        @tube
        class DeferredTube(object):
            def received(self, data):
                yield d

        fakeDrain = self.fd
        self.ff.flowTo(series(DeferredTube(),
                              deferredToResult())).flowTo(fakeDrain)
        self.ff.drain.receive("ignored")

        anPause = self.fd.fount.pauseFlow()

        d.callback("hello")
        self.assertEquals(self.fd.received, [])

        anPause.unpause()
        self.assertEquals(self.fd.received, ["hello"])


    def test_tubeStoppedDeferredly(self):
        """
        The L{_Siphon} stops its L{Tube} and propagates C{flowStopped}
        downstream upon the completion of all L{Deferred}s returned from its
        L{Tube}'s C{stopped} implementation.
        """
        reasons = []
        conclusion = Deferred()
        @tube
        class SlowEnder(object):
            def stopped(self, reason):
                reasons.append(reason)
                yield conclusion

        self.ff.flowTo(series(SlowEnder(), deferredToResult(), self.fd))
        self.assertEquals(reasons, [])
        self.assertEquals(self.fd.received, [])

        stopReason = Failure(ZeroDivisionError())

        self.ff.drain.flowStopped(stopReason)
        self.assertEquals(self.fd.received, [])
        self.assertEquals(len(reasons), 1)
        self.assertIdentical(reasons[0].type, ZeroDivisionError)
        self.assertEqual(self.fd.stopped, [])

        conclusion.callback("conclusion")
        # Now it's really done.
        self.assertEquals(self.fd.received, ["conclusion"])
        self.assertEqual(self.fd.stopped, [stopReason])


    def test_fountToDeferred(self):
        """
        L{fountToDeferred} returns a L{Deferred} that fires with an iterable of
        all the objects that the fount passed to it emits.
        """
        self.assertIsNone(self.ff.drain)
        d = fountToDeferred(self.ff)
        self.assertIsNotNone(self.ff.drain)
        self.assertNoResult(d)
        self.ff.drain.receive(1)
        self.assertNoResult(d)
        self.ff.drain.receive(2)
        self.ff.drain.flowStopped(Failure(ZeroDivisionError()))
        self.assertEqual(list(self.successResultOf(d)), [1, 2])
