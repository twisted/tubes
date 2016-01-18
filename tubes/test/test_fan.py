# -*- test-case-name: tubes.test.test_fan -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.fan}.
"""

from zope.interface.verify import verifyObject

from twisted.trial.unittest import SynchronousTestCase

from ..itube import IFount, IDrain

from ..test.util import FakeFount, FakeDrain
from ..tube import receiver, series
from ..fan import Out, In, Thru


class FakeIntermediateDrain(FakeDrain):
    """
    An intermediate drain that returns a subsequent fount, for debugging
    tube-like transceivers with more explicit ordering.
    """

    nextStep = FakeFount()

    def flowingFrom(self, something):
        """
        This drain should accept some input and allege that it returns some
        output.

        @param something: A fount.

        @return: C{self.nextStep}
        """
        super(FakeIntermediateDrain, self).flowingFrom(something)
        return self.nextStep



class FanOutTests(SynchronousTestCase):
    """
    Tests for L{tubes.fan.Out}
    """

    def test_outFountFlowTo(self):
        """
        L{Out.newFount}'s C{flowTo} calls C{flowingFrom} on its drain and
        returns the result.
        """
        out = Out()
        aFount = out.newFount()
        aFakeDrain = FakeIntermediateDrain()
        result = aFount.flowTo(aFakeDrain)
        self.assertIdentical(aFakeDrain.fount, aFount)
        self.assertIdentical(result, aFakeDrain.nextStep)


    def test_verifyCompliance(self):
        """
        L{Out.newFount} and L{Out.drain} adhere to their respected declared
        interfaces.
        """
        out = Out()
        verifyObject(IFount, out.newFount())
        verifyObject(IDrain, out.drain)


    def test_fanOut(self):
        """
        When an L{Out} is constructed and flowed to two drains, both drains
        receive the same value passed to L{Out.drain}'s C{receive} method.
        """
        ff = FakeFount()
        fdA = FakeDrain()
        fdB = FakeDrain()

        out = Out()
        fountA = out.newFount()
        fountB = out.newFount()
        nothing = ff.flowTo(out.drain)
        self.assertIdentical(nothing, None)

        fountA.flowTo(fdA)
        fountB.flowTo(fdB)
        ff.drain.receive("foo")

        self.assertEquals(fdA.received, ["foo"])
        self.assertEquals(fdB.received, ["foo"])


    def test_fanReceivesBeforeFountsHaveDrains(self):
        """
        L{Out.drain}'s C{receive} method only relays outputs to founts which
        are presently attached.
        """
        ff = FakeFount()
        fd = FakeDrain()

        out = Out()
        fount = out.newFount()

        ff.flowTo(out.drain)

        ff.drain.receive("foo")

        fount.flowTo(fd)
        self.assertEquals(fd.received, [])


    def test_pausingOneOutFountPausesUpstreamFount(self):
        """
        When one fount created by L{Out.newFount} is paused, the fount flowing
        to L{Out.drain} is paused.
        """
        ff = FakeFount()
        out = Out()
        fount = out.newFount()

        ff.flowTo(out.drain)

        fount.pauseFlow()
        self.assertEquals(ff.flowIsPaused, 1)


    def test_oneFountPausesInReceive(self):
        """
        When an L{Out} has two founts created by C{newFount} fA and fB, and
        they are flowing to two drains, dA and dB, if dA pauses its fount
        during C{receive(X)}, C{X} will still be delivered to dB, because dB
        hasn't paused.
        """
        ff = FakeFount()
        out = Out()
        fountA = out.newFount()
        fountB = out.newFount()
        class PausingDrain(FakeDrain):
            def receive(self, item):
                super(PausingDrain, self).receive(item)
                self.fount.pauseFlow()
        pausingDrain = PausingDrain()
        fountA.flowTo(pausingDrain)
        fakeDrain = FakeDrain()
        fountB.flowTo(fakeDrain)
        ff.flowTo(out.drain)
        ff.drain.receive("something")
        self.assertEqual(pausingDrain.received, ["something"])
        self.assertEqual(fakeDrain.received, ["something"])
        self.assertEqual(ff.flowIsPaused, 1)


    def test_oneFountPausesOthersInReceive(self):
        """
        When an L{Out} has two founts created by C{newFount} fA and fB, and
        they are flowing to two drains, dA and dB, if dA pauses both founts
        during C{receive(X)}, C{X} will I{not} be delivered to dB, because fB
        is paused by the time that call would be made.  Unpausing both will
        cause it to get delivered.
        """
        ff = FakeFount()
        out = Out()
        fountA = out.newFount()
        fountB = out.newFount()
        pauses = []
        class PauseEverybody(FakeDrain):
            def receive(self, item):
                super(PauseEverybody, self).receive(item)
                pauses.append(fountA.pauseFlow())
                pauses.append(fountB.pauseFlow())
        ff.flowTo(out.drain)
        fountA.flowTo(PauseEverybody())
        fd = FakeDrain()
        fountB.flowTo(fd)
        ff.drain.receive("something")
        self.assertEqual(fd.received, [])
        for pause in pauses:
            pause.unpause()
        self.assertEqual(fd.received, ["something"])


    def test_oneFountStops(self):
        """
        When one fount created by L{Out.newFount} is stopped, only the drain
        for that fount is affected; others continue receiving values.
        """
        ff = FakeFount()
        out = Out()
        fountA = out.newFount()
        fountB = out.newFount()
        ff.flowTo(out.drain)

        fdA = FakeDrain()
        fdB = FakeDrain()

        fountA.flowTo(fdA)
        fountB.flowTo(fdB)

        ff.drain.receive("before")
        fdA.fount.stopFlow()
        ff.drain.receive("after")
        self.assertEqual(fdA.received, ["before"])
        self.assertEqual(fdB.received, ["before", "after"])


    def test_oneFountStopsInReceive(self):
        """
        When one fount created by L{Out.newFount} is stopped in its drain's
        C{receive} method, only the drain for that fount is affected; others
        continue receiving values.
        """
        ff = FakeFount()
        out = Out()
        fountA = out.newFount()
        fountB = out.newFount()
        class StoppingDrain(FakeDrain):
            def receive(self, item):
                super(StoppingDrain, self).receive(item)
                self.fount.stopFlow()
        stoppingDrain = StoppingDrain()
        fountA.flowTo(stoppingDrain)
        fakeDrain = FakeDrain()
        fountB.flowTo(fakeDrain)
        ff.flowTo(out.drain)
        ff.drain.receive("something")
        self.assertEqual(stoppingDrain.received, ["something"])
        self.assertEqual(fakeDrain.received, ["something"])

        ff.drain.receive("something else")
        self.assertEqual(stoppingDrain.received, ["something"])
        self.assertEqual(fakeDrain.received, ["something", "something else"])

        self.assertFalse(ff.flowIsStopped)


    def test_switchFlowToNone(self):
        """
        When L{out.drain} removes its upstream fount, it unpauses it.
        """
        out = Out()
        upstream1 = FakeFount()
        upstream1.flowTo(out.drain)
        out.newFount().pauseFlow()
        out.drain.flowingFrom(None)
        self.assertEqual(upstream1.flowIsPaused, False)


    def test_flowStopped(self):
        """
        When the flow stops to L{out.drain}, it stops to all downstream drains
        as well, with the same reason.
        """
        out = Out()
        upstream1 = FakeFount()
        upstream1.flowTo(out.drain)
        fount1 = out.newFount()
        fount2 = out.newFount()
        downstream1 = FakeDrain()
        downstream2 = FakeDrain()
        fount1.flowTo(downstream1)
        fount2.flowTo(downstream2)
        out.drain.flowStopped(4321)
        self.assertEqual(downstream1.stopped, [4321])
        self.assertEqual(downstream2.stopped, [4321])



class FanInTests(SynchronousTestCase):
    """
    Tests for L{tubes.fan.In}.
    """

    def test_oneDrainReceives(self):
        """
        When one drain created by L{In.newDrain} recives a value, the drain
        that L{In.fount} is flowing to receives that value.
        """
        fd = FakeDrain()
        fanIn = In()
        fanIn.fount.flowTo(fd)
        ff = FakeFount()
        ff.flowTo(fanIn.newDrain())
        ff.drain.receive("testing")
        self.assertEqual(fd.received, ["testing"])


    def test_pauseWhenNoDrain(self):
        """
        When a drain created by L{In.newDrain} is hooked up to a new fount, but
        that L{In.fount} isn't flowing to anything yet, the new fount will be
        paused immediately; when the L{In.fount} receives a drain, it is
        unpaused.
        """
        ff = FakeFount()
        fanIn = In()
        ff.flowTo(fanIn.newDrain())
        self.assertEqual(ff.flowIsPaused, True)
        fanIn.fount.flowTo(FakeDrain())
        self.assertEqual(ff.flowIsPaused, False)


    def test_pauseNewFountWhenPaused(self):
        """
        When a drain created by L{In.newDrain} receives a new fount, if
        L{In.fount} is already paused, the fount flowed to the new drain will
        also be paused.
        """
        fanIn = In()
        fd = FakeDrain()
        fanIn.fount.flowTo(fd)
        f1 = FakeFount()
        f1.flowTo(fanIn.newDrain())
        self.assertEqual(f1.flowIsPaused, False)
        anPause = fd.fount.pauseFlow()
        self.assertEqual(f1.flowIsPaused, True)
        f2 = FakeFount()
        self.assertEqual(f2.flowIsPaused, False)
        f2.flowTo(fanIn.newDrain())
        self.assertEqual(f2.flowIsPaused, True)
        anPause.unpause()
        self.assertEqual(f2.flowIsPaused, False)


    def test_dontUnpauseWhenNoDrain(self):
        """
        L{In.fount}C{.flowTo(None)} won't unpause L{In}'s upstream founts.
        """
        fanIn = In()
        ff = FakeFount()
        ff.flowTo(fanIn.newDrain())
        self.assertEqual(ff.flowIsPaused, True)
        fanIn.fount.flowTo(None)
        self.assertEqual(ff.flowIsPaused, True)


    def test_pauseWhenSwitchedToNoDrain(self):
        """
        L{In.fount}C{.flowTo(None)} after L{In.fount} already has a drain will
        pause all the upstream founts.
        """
        fanIn = In()
        downstream = FakeDrain()
        fanIn.fount.flowTo(downstream)
        upstream1 = FakeFount()
        upstream2 = FakeFount()
        upstream1.flowTo(fanIn.newDrain())
        upstream2.flowTo(fanIn.newDrain())
        fanIn.fount.flowTo(None)
        self.assertEqual(upstream1.flowIsPaused, True)
        self.assertEqual(upstream2.flowIsPaused, True)


    def test_flowStopped(self):
        """
        When the flow stops to one of the drains returned by L{In.newDrain}, it
        removes the associated fount from the list of founts to be paused.
        """
        fanIn = In()
        downstream = FakeDrain()
        fanIn.fount.flowTo(downstream)
        upstream1 = FakeFount()
        upstream2 = FakeFount()
        upstream1.flowTo(fanIn.newDrain())
        upstream2.flowTo(fanIn.newDrain())

        upstream1.drain.flowStopped(None)

        # Sanity check.
        self.assertEqual(upstream1.flowIsPaused, False)
        self.assertEqual(upstream2.flowIsPaused, False)

        pause = downstream.fount.pauseFlow()

        self.assertEqual(upstream1.flowIsPaused, False)
        self.assertEqual(upstream2.flowIsPaused, True)

        pause.unpause()

        self.assertEqual(upstream1.flowIsPaused, False)
        self.assertEqual(upstream2.flowIsPaused, False)


    def test_stopFlow(self):
        """
        When the drain of L{In.fount} stops its upstream flow, that stops the
        flow of every attached fount.
        """
        fanIn = In()
        downstream = FakeDrain()
        fanIn.fount.flowTo(downstream)

        upstream1 = FakeFount()
        upstream2 = FakeFount()

        upstream1.flowTo(fanIn.newDrain())
        upstream2.flowTo(fanIn.newDrain())

        # Sanity check
        self.assertEqual(upstream1.flowIsStopped, False)
        self.assertEqual(upstream2.flowIsStopped, False)

        downstream.fount.stopFlow()

        self.assertEqual(upstream1.flowIsStopped, True)
        self.assertEqual(upstream2.flowIsStopped, True)



class FanThruTests(SynchronousTestCase):
    """
    Tests for L{Thru}.
    """

    def test_thru(self):
        """
        Each input provided to L{Thru} will be sent to each of its drains, and
        the outputs of those then sent on to its downstream drain in order.
        """
        @receiver()
        def timesTwo(input):
            yield input * 2
        @receiver()
        def timesThree(input):
            yield input * 3

        ff = FakeFount()
        fd = FakeDrain()

        ff.flowTo(Thru([series(timesTwo),
                        series(timesThree)])).flowTo(fd)
        ff.drain.receive(1)
        ff.drain.receive(2)
        ff.drain.receive(3)
        self.assertEqual(fd.received,
                         [1*2, 1*3, 2*2, 2*3, 3*2, 3*3])

