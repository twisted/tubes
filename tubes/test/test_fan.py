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
from ..fan import Out


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
