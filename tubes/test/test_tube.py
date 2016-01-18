# -*- test-case-name: tubes.test.test_tube -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.tube}.
"""

from __future__ import print_function

from zope.interface import implementer
from zope.interface.declarations import directlyProvides
from zope.interface.verify import verifyObject

from twisted.trial.unittest import SynchronousTestCase as TestCase

from twisted.python.failure import Failure

from ..itube import IDivertable, ITube, IFount
from ..tube import tube, series, Diverter

# Currently, this private implementation detail is imported only to test the
# repr.  Is it *possible* to even get access to a _Siphon via the public
# interface?  When would you see this repr?  Hmm. -glyph
from .._siphon import _Siphon

from ..test.util import (TesterTube, FakeFount, FakeDrain, IFakeInput,
                         IFakeOutput, NullTube, PassthruTube, ReprTube,
                         FakeFountWithBuffer)



class TubeTests(TestCase):
    """
    Tests for L{Tube}'s various no-ops.
    """

    def test_provider(self):
        """
        L{Tube} provides L{ITube}.
        """
        self.failUnless(verifyObject(ITube, NullTube()))


    def test_noOps(self):
        """
        All of L{Tube}'s implementations of L{ITube} are no-ops.
        """
        # There are no assertions here because there's no reasonable way this
        # test will fail rather than error; however, coverage --branch picks up
        # on methods which haven't been executed and the fact that these
        # methods exist (i.e. for super() to invoke them) is an important
        # property to verify. -glyph

        # TODO: maybe make a policy of this or explain it somewhere other than
        # a comment.  Institutional learning ftw.

        tube = NullTube()
        tube.started()
        tube.received(None)
        tube.stopped(None)



@tube
class Starter(object):
    """
    A tube that yields a greeting.
    """

    def started(self):
        """
        Yield a greeting.
        """
        yield "greeting"



class SeriesTests(TestCase):
    """
    Tests for L{series}.
    """

    def setUp(self):
        """
        Create a siphon, and a fake drain and fount connected to it.
        """
        self.tube = TesterTube()
        self.siphonDrain = series(self.tube)
        self.ff = FakeFount()
        self.fd = FakeDrain()


    def test_tubeStarted(self):
        """
        The L{_Siphon} starts its L{Tube} upon C{flowingFrom}.
        """

        self.ff.flowTo(series(Starter(), self.fd))
        self.assertEquals(self.fd.received, ["greeting"])


    def test_startedFlowingToAnother(self):
        """
        The greeting is relayed to the ultimate drain when a tube in the middle
        of a series adds a greeting via C{started}.
        """
        self.ff.flowTo(
            series(PassthruTube(), Starter(), PassthruTube())
        ).flowTo(self.fd)
        self.assertEqual(self.fd.received, ["greeting"])


    def test_noDrainThenLoseFount(self):
        """
        If a fount is flowed to a tube which does not yet have a drain, then
        flowed to another place, it will not be paused.
        """
        drainless = series(PassthruTube())
        self.ff.flowTo(drainless)
        self.ff.drain.receive(object())
        self.assertEqual(self.ff.flowIsPaused, True)
        ff2 = FakeFount()
        ff2.flowTo(drainless)
        self.assertIs(ff2.drain, drainless)
        self.assertEqual(ff2.flowIsPaused, True)
        self.assertEqual(self.ff.drain, None)
        self.assertEqual(self.ff.flowIsPaused, False)
        self.assertEqual(ff2.flowIsPaused, True)


    def test_siphonFlowingFromReturnsSelfFount(self):
        """
        L{_SiphonDrain.flowingFrom} initially returns its L{_Siphon}'s
        downstream fount.
        """
        drain = series(PassthruTube())
        self.assertIdentical(drain.flowingFrom(self.ff),
                             drain._siphon._tfount)


    def test_siphonFlowingFromNoneReturnsSelfFount(self):
        """
        L{_SiphonDrain.flowingFrom} initially returns its L{_Siphon}'s
        downstream fount when passed L{None} as well.
        """
        drain = series(PassthruTube())
        self.assertIdentical(drain.flowingFrom(None),
                             drain._siphon._tfount)


    def test_siphonFlowingFromSomethingThenNothing(self):
        """
        L{_SiphonDrain.flowingFrom} sets L{_SiphonDrain.fount}, whether it is
        passed a valid L{IFount} (one with matching input/output types) or
        L{None}.
        """
        drain = series(PassthruTube())
        drain.flowingFrom(self.ff)
        self.assertIdentical(drain.fount, self.ff)
        drain.flowingFrom(None)
        self.assertIdentical(drain.fount, None)


    def test_siphonFlowingFromReturnsNextFount(self):
        """
        Once L{_SiphonFount.flowTo} has been called,
        L{_SiphonDrain.flowingFrom} returns the next fount in the chain.
        """
        drain = series(PassthruTube())
        fount = drain.flowingFrom(self.ff)
        drain2 = series(PassthruTube())
        fount2 = fount.flowTo(drain2)
        self.assertIdentical(fount2,
                             drain2._siphon._tfount)

        # Since flowTo implicitly calls flowingFrom the result should be the
        # same, but since we're directly testing flowingFrom let's directly
        # test it.
        self.assertIdentical(drain.flowingFrom(self.ff),
                             drain2._siphon._tfount)


    def test_tubeReStarted(self):
        """
        It's perfectly valid to take a L{_Siphon} and call C{flowingFrom} with
        the same drain it's already flowing to.

        This will happen any time that a series is partially constructed and
        then flowed to a new drain.
        """
        @tube
        class ReStarter(object):
            startedCount = 0
            def started(self):
                count = self.startedCount
                self.startedCount += 1
                yield ("re" * count) + "greeting"

        aStarter = ReStarter()
        srs = series(PassthruTube(), aStarter,
                     PassthruTube())
        nextFount = self.ff.flowTo(srs)
        self.assertEqual(self.ff.flowIsPaused, 1)
        nextFount.flowTo(self.fd)
        self.assertEqual(self.ff.flowIsPaused, 0)
        self.assertEqual(self.fd.received, ["greeting"])
        self.assertEqual(aStarter.startedCount, 1)


    def test_tubeStopped(self):
        """
        The L{_Siphon} stops its L{Tube} and propagates C{flowStopped}
        downstream upon C{flowStopped}.
        """
        reasons = []
        @tube
        class Ender(object):
            def stopped(self, reason):
                reasons.append(reason)
                yield "conclusion"

        self.ff.flowTo(series(Ender(), self.fd))
        self.assertEquals(reasons, [])
        self.assertEquals(self.fd.received, [])

        stopReason = Failure(ZeroDivisionError())

        self.ff.drain.flowStopped(stopReason)
        self.assertEquals(self.fd.received, ["conclusion"])
        self.assertEquals(len(reasons), 1)
        self.assertIdentical(reasons[0].type, ZeroDivisionError)

        self.assertEqual(self.fd.stopped, [stopReason])


    def test_tubeDiverting(self):
        """
        The L{_Siphon} of a L{Tube} sends on data to a newly specified
        L{IDrain} when its L{IDivertable.divert} method is called.
        """
        @implementer(IDivertable)
        class DivertablePassthruTube(PassthruTube):
            def reassemble(self, data):
                return data

        diverter = Diverter(DivertablePassthruTube())
        fakeDrain = self.fd
        testCase = self

        @tube
        class Switcher(object):
            def received(self, data):
                # Sanity check: this should be the only input ever received.
                testCase.assertEqual(data, "switch")
                diverter.divert(series(Switchee(), fakeDrain))
                return ()

        @tube
        class Switchee(object):
            def received(self, data):
                yield "switched " + data

        self.ff.flowTo(diverter).flowTo(series(Switcher(), fakeDrain))
        self.ff.drain.receive("switch")
        self.ff.drain.receive("to switchee")
        self.assertEquals(fakeDrain.received, ["switched to switchee"])


    def test_tubeDivertingReassembly(self):
        """
        The L{_Siphon} of a L{Tube} sends on reassembled data - the return
        value of L{Tube.reassemble} to a newly specified L{Drain}; it is only
        called with un-consumed elements of data (those which have never been
        passed to C{receive}).
        """
        preSwitch = []
        @implementer(IDivertable)
        @tube
        class ReassemblingTube(object):
            def received(self, datum):
                nonBorks = datum.split("BORK")
                return nonBorks

            def reassemble(self, data):
                for element in data:
                    yield '(bork was here)'
                    yield element

        @tube
        class Switcher(object):
            def received(self, data):
                # Sanity check: this should be the only input ever received.
                preSwitch.append(data)
                diverter.divert(series(Switchee(), fakeDrain))
                return ()

        @tube
        class Switchee(object):
            def received(self, data):
                yield "switched " + data

        diverter = Diverter(ReassemblingTube())
        fakeDrain = self.fd
        self.ff.flowTo(diverter).flowTo(series(Switcher(), fakeDrain))

        self.ff.drain.receive("beforeBORKto switchee")

        self.assertEqual(preSwitch, ["before"])
        self.assertEqual(self.fd.received, ["switched (bork was here)",
                                            "switched to switchee"])


    def test_diverterInYourDiverterSoYouCanDivertWhileYouDivert(self):
        """
        When L{IDivertable.reassemble} returns multiple values, the argument to
        L{Diverter.divert}, B, may itself call L{Diverter.divert} with a drain
        C to redirect the flow as it's receiving those values and subsequent
        values will be delivered to C{C.receive}.
        """
        finalDrain = self.fd

        @implementer(IDivertable)
        @tube
        class FirstDivertable(object):
            def received(self, datum):
                firstDiverter.divert(secondDiverter)

            def reassemble(self, data):
                yield "more data"
                yield "yet more data"

        firstDiverter = Diverter(FirstDivertable())

        @implementer(IDivertable)
        @tube
        class SecondDivertable(object):
            def received(self, datum):
                secondDiverter.divert(finalDrain)
                return []

            def reassemble(self, data):
                return []

        secondDiverter = Diverter(SecondDivertable())
        self.ff.flowTo(firstDiverter)
        self.ff.drain.receive("first data")
        self.assertEqual(finalDrain.received, ["yet more data"])


    def test_divertWhilePaused(self):
        """
        If an L{IDivertable} L{tube} is diverted while it is paused,
        L{reassemble} will still be passed the rest of the values.
        """
        @implementer(IDivertable)
        @tube
        class SlowDivertable(object):
            def received(self, datums):
                for datum in datums.split(" "):
                    yield datum

            def reassemble(self, datums):
                return [" ".join(datums)]

        diverter = Diverter(SlowDivertable())
        class PausingDrain(FakeDrain):
            def receive(self, item):
                result = super(PausingDrain, self).receive(item)
                self.pause = self.fount.pauseFlow()
                return result
        dtp = PausingDrain()
        self.ff.flowTo(diverter).flowTo(dtp)
        self.ff.drain.receive("foo bar baz")
        diverter.divert(self.fd)
        self.assertEqual(dtp.received, ["foo"])
        self.assertEqual(self.fd.received, ["bar baz"])


    def test_tubeDivertingControlsWhereOutputGoes(self):
        """
        If a siphon A with a tube Ap is flowing to a siphon B with a divertable
        tube Bp, Ap.received may switch B to a drain C, and C will receive any
        outputs produced by that received call; B (and Bp) will not.
        """
        @tube
        class Switcher(object):
            def received(self, data):
                if data == "switch":
                    yield "diverting"
                    diverter.divert(series(Switchee(), fakeDrain))
                    yield "switched"
                else:
                    yield data

        @tube
        class Switchee(object):
            def received(self, data):
                yield "switched({0})".format(data)

        fakeDrain = self.fd
        destinationTube = PassthruTube()
        # `reassemble` should not be called, so don't implement it
        directlyProvides(destinationTube, IDivertable)
        diverter = Diverter(PassthruTube())

        firstDrain = series(Switcher(), diverter)
        self.ff.flowTo(firstDrain).flowTo(fakeDrain)
        self.ff.drain.receive("before")
        self.ff.drain.receive("switch")
        self.ff.drain.receive("after")
        self.assertEqual(self.fd.received,
                         ["before", "diverting",
                          "switched(switched)",
                          "switched(after)"])


    def test_tubePausesItself(self):
        """
        When one of the methods on L{Tube} pauses its own C{fount} or C{drain},
        the next item it yields will not arrive at its downstream drain until
        it is unpaused.
        """
        @tube
        class PauseThenYield(object):
            def started(self):
                yield 1
                self.pause = meAsFount.pauseFlow()
                yield 2
                yield 3

        pty = PauseThenYield()
        meAsFount = self.ff.flowTo(series(pty))
        meAsFount.flowTo(self.fd)
        self.assertEqual(self.fd.received, [1])
        pty.pause.unpause()
        self.assertEqual(self.fd.received, [1, 2, 3])


    def test_initiallyEnthusiasticFountBecomesDisillusioned(self):
        """
        If an L{IFount} provider synchronously calls C{receive} on a
        L{_SiphonDrain}, whose corresponding L{_SiphonFount} is not flowing to
        an L{IDrain} yet, it will be synchronously paused with
        L{IFount.pauseFlow}; when that L{_SiphonFount} then flows to something
        else, the buffer will be unspooled.
        """
        ff = FakeFountWithBuffer()
        ff.bufferUp("something")
        ff.bufferUp("else")
        newDrain = series(PassthruTube())
        # Just making sure.
        self.assertEqual(ff.flowIsPaused, False)
        newFount = ff.flowTo(newDrain)
        self.assertEqual(ff.flowIsPaused, True)
        # `something` should have been un-buffered at this point.
        self.assertEqual(ff.buffer, ["else"])
        newFount.flowTo(self.fd)
        self.assertEqual(self.fd.received, ["something", "else"])
        self.assertEqual(ff.buffer, [])
        self.assertEqual(ff.flowIsPaused, False)


    def test_flowToNoneInitialNoOp(self):
        """
        L{_SiphonFount.flowTo}C{(None)} is a no-op when called before
        any other invocations of L{_SiphonFount.flowTo}.
        """
        siphonFount = self.ff.flowTo(self.siphonDrain)
        self.assertEquals(siphonFount.drain, None)
        siphonFount.flowTo(None)


    def test_tubeDiverting_ReEntrantResumeReceive(self):
        """
        Diverting a tube that is receiving data from a fount which
        synchronously produces some data to C{receive} will ... uh .. work.
        """
        @tube
        class Switcher(object):
            def received(self, data):
                if data == "switch":
                    diverter.divert(series(Switchee(), fakeDrain))
                    return None
                else:
                    return [data]

        @tube
        class Switchee(object):
            def received(self, data):
                yield "switched " + data

        fakeDrain = self.fd
        destinationTube = PassthruTube()
        # `reassemble` should not be called, so don't implement it
        directlyProvides(destinationTube, IDivertable)

        diverter = Diverter(destinationTube)

        firstDrain = series(Switcher(), diverter)

        ff = FakeFountWithBuffer()
        ff.bufferUp("before")
        ff.bufferUp("switch")
        ff.bufferUp("after")
        nf = ff.flowTo(firstDrain)
        nf.flowTo(fakeDrain)
        self.assertEquals(self.fd.received, ["before", "switched after"])


    def test_tubeDiverting_LotsOfStuffAtOnce(self):
        """
        If a tube returns a sequence of multiple things, great.

        (This is a test for diverting when a receive method has returned
        multiple things.)
        """
        # TODO: docstring.
        @implementer(IDivertable)
        class DivertablePassthruTube(PassthruTube):
            """
            Reassemble should not be called; don't implement it.
            """

        @tube
        class Multiplier(object):
            def received(self, datums):
                return datums

        @tube
        class Switcher(object):
            def received(self, data):
                if data == "switch":
                    diverter.divert(series(Switchee(), fakeDrain))
                    return None
                else:
                    return [data]

        @tube
        class Switchee(object):
            def received(self, data):
                yield "switched " + data

        fakeDrain = self.fd
        diverter = Diverter(DivertablePassthruTube())

        firstDrain = series(Multiplier(), Switcher(), diverter)

        self.ff.flowTo(firstDrain).flowTo(fakeDrain)
        self.ff.drain.receive(["before", "switch", "after"])
        self.assertEquals(self.fd.received, ["before", "switched after"])


    def test_flowingFromFirst(self):
        """
        If L{_Siphon.flowingFrom} is called before L{_Siphon.flowTo}, the
        argument to L{_Siphon.flowTo} will immediately have its
        L{IDrain.flowingFrom} called.
        """
        self.ff.flowTo(self.siphonDrain).flowTo(self.fd)
        self.assertNotIdentical(self.fd.fount, None)


    def test_siphonReceiveCallsTubeReceived(self):
        """
        L{_SiphonDrain.receive} will call C{tube.received} and synthesize a
        fake "0.5" progress result if L{None} is returned.
        """
        got = []
        @tube
        class ReceivingTube(object):
            def received(self, item):
                got.append(item)
        drain = series(ReceivingTube())
        drain.receive("sample item")
        self.assertEqual(got, ["sample item"])


    def test_flowFromTypeCheckFails(self):
        """
        L{_Siphon.flowingFrom} checks the type of its input.  If it doesn't
        match (both are specified explicitly, and they don't match).
        """
        @tube
        class ToTube(object):
            inputType = IFakeInput
        siphonDrain = series(ToTube())
        self.ff.outputType = IFakeOutput
        self.failUnlessRaises(TypeError, self.ff.flowTo, siphonDrain)
        self.assertIdentical(siphonDrain.fount, None)


    def test_flowFromTypeCheckSucceeds(self):
        """
        L{_Siphon.flowingFrom} checks the type of its input.  If it doesn't
        match (both are specified explicitly, and they don't match).
        """
        @tube
        class ToTube(object):
            inputType = IFakeOutput
        siphonDrain = series(ToTube())
        obj = self.ff.flowTo(siphonDrain)
        self.assertTrue(IFount.providedBy(obj))


    def test_receiveIterableDeliversDownstream(self):
        """
        When L{Tube.received} yields a value, L{_Siphon} will call L{receive}
        on its downstream drain.
        """
        self.ff.flowTo(series(PassthruTube())).flowTo(self.fd)
        self.ff.drain.receive(7)
        self.assertEquals(self.fd.received, [7])


    def test_receiveCallsTubeReceived(self):
        """
        L{_SiphonDrain.receive} will send its input to L{ITube.received} on its
        tube.
        """
        self.siphonDrain.receive("one-item")
        self.assertEquals(self.tube.allReceivedItems, ["one-item"])


    def test_flowToWillNotResumeFlowPausedInFlowingFrom(self):
        """
        L{_SiphonFount.flowTo} will not call L{_SiphonFount.resumeFlow} when
        it's L{IDrain} calls L{IFount.pauseFlow} in L{IDrain.flowingFrom}.
        """
        class PausingDrain(FakeDrain):
            def flowingFrom(self, fount):
                self.fount = fount
                self.fount.pauseFlow()

        self.ff.flowTo(self.siphonDrain).flowTo(PausingDrain())

        self.assertTrue(self.ff.flowIsPaused, "Upstream is not paused.")


    def test_reentrantFlowTo(self):
        """
        An L{IDrain} may call its argument's L{_SiphonFount.flowTo} method in
        L{IDrain.flowingFrom} and said fount will be flowing to the new drain.
        """
        testFD = self.fd

        class ReflowingDrain(FakeDrain):
            def flowingFrom(self, fount):
                self.fount = fount
                if fount is not None:
                    self.fount.flowTo(testFD)

        nf = self.ff.flowTo(series(PassthruTube()))
        nf.flowTo(ReflowingDrain())

        self.ff.drain.receive("hello")
        self.assertEqual(self.fd.received, ["hello"])


    def test_drainPausesFlowWhenPreviouslyPaused(self):
        """
        L{_SiphonDrain.flowingFrom} will pause its fount if its L{_SiphonFount}
        was previously paused, and unpause its old fount.
        """
        newFF = FakeFount()
        pauses = []

        pauses.append(self.ff.flowTo(self.siphonDrain).pauseFlow())
        newFF.flowTo(self.siphonDrain)

        self.assertFalse(self.ff.flowIsPaused, "Old fount still paused.")
        self.assertTrue(newFF.flowIsPaused, "New upstream is not paused.")


    def test_drainFlowingFromNoneAlsoUnpauses(self):
        """
        L{_SiphonDrain.flowingFrom} will resume its old fount when flowed to
        L{None}.
        """
        self.ff.flowTo(self.siphonDrain).pauseFlow()
        self.siphonDrain.flowingFrom(None)
        self.assertFalse(self.ff.flowIsPaused, "Old fount still paused.")


    def test_drainRemainsPausedAcrossDetachedState(self):
        """
        L{_SiphonDrain.flowingFrom} will pause its fount if its L{_SiphonFount}
        was previously paused, prior to being in a detached state by having
        L{_SiphonDrain.flowingFrom} called with C{None}.
        """
        newFF = FakeFount()

        self.ff.flowTo(self.siphonDrain).pauseFlow()
        self.siphonDrain.flowingFrom(None)
        newFF.flowTo(self.siphonDrain)
        self.assertTrue(newFF.flowIsPaused, "New upstream is not paused.")


    def test_siphonDrainRepr(self):
        """
        repr for L{_SiphonDrain} includes a reference to its tube.
        """

        self.assertEqual(repr(series(ReprTube())),
                         '<Drain for <Tube for Testing>>')


    def test_siphonFountRepr(self):
        """
        repr for L{_SiphonFount} includes a reference to its tube.
        """

        fount = FakeFount()

        self.assertEqual(repr(fount.flowTo(series(ReprTube()))),
                         '<Fount for <Tube for Testing>>')


    def test_siphonRepr(self):
        """
        repr for L{_Siphon} includes a reference to its tube.
        """

        tube = ReprTube()

        self.assertEqual(repr(_Siphon(tube)),
                         '<_Siphon for <Tube for Testing>>')


    def test_diverterRepr(self):
        """
        repr for L{Diverter} includes a reference to its tube.
        """
        diverter = Diverter(ReprTube())
        self.assertEqual(repr(diverter),
                         "<Diverter for <Tube for Testing>>")


    def test_stopFlow(self):
        """
        L{_SiphonFount.stopFlow} stops the flow of its L{_Siphon}'s upstream
        fount.
        """
        self.ff.flowTo(series(self.siphonDrain, self.fd))
        self.assertEquals(self.ff.flowIsStopped, False)
        self.fd.fount.stopFlow()
        self.assertEquals(self.ff.flowIsStopped, True)


    def test_stopFlowInterruptsStarted(self):
        """
        As per L{IFount.stopFlow}, a compliant L{fount <IFount>} never calls
        C{received} on its C{drain} after receiving a C{stopFlow} request; so,
        when a L{tube} yields multiple values from C{started}, only those
        delivered before C{stopFlow} is called should be delivered.
        """
        @tube
        class OneTwo(object):
            def started(self):
                yield 1
                yield 2

        class Stopper(FakeDrain):
            def receive(self, item):
                super(Stopper, self).receive(item)
                self.fount.stopFlow()

        stopper = Stopper()
        self.ff.flowTo(series(OneTwo())).flowTo(stopper)
        self.assertEqual(stopper.received, [1])


    def test_stopFlowStopsFlowImmediately(self):
        """
        Similar to L{test_stopFlowInterruptsStarted}, if the upstream fount
        calls C{flowStopped} within its C{stopFlow} implementation.
        """
        class FastStopper(FakeFount):
            def stopFlow(self):
                super(FastStopper, self).stopFlow()
                self.drain.flowStopped(Failure(ZeroDivisionError()))

        noFurther = []
        @tube
        class OneTwo(object):
            def started(self):
                yield 1
                noFurther.append(True)
                yield 2

        class Stopper(FakeDrain):
            def receive(self, item):
                super(Stopper, self).receive(item)
                self.fount.stopFlow()

        ff = FastStopper()
        stopper = Stopper()
        ff.flowTo(series(OneTwo())).flowTo(stopper)
        self.assertEqual(stopper.received, [1])
        self.assertEqual(len(stopper.stopped), 1)
        self.assertEqual(stopper.stopped[0].type, ZeroDivisionError)
        self.assertFalse(
            noFurther,
            "kept iterating started() after it was done")


    def test_stopFlowBeforeFlowBegins(self):
        """
        L{_SiphonFount.stopFlow} will stop the flow of its L{_Siphon}'s
        upstream fount later, when it acquires one, if it's previously been
        stopped.
        """
        partially = series(self.siphonDrain, self.fd)
        self.fd.fount.stopFlow()
        self.ff.flowTo(partially)
        self.assertEquals(self.ff.flowIsStopped, True)


    def test_stopFlowWhileStartingFlow(self):
        """
        If a fount flowing to a tube calls C{flowStopped} in C{flowTo}, the
        results of C{started} and C{stopped} on the tube should both show up to
        its drain.
        """
        class JustStop(FakeFount):
            def flowTo(self, drain):
                result = super(JustStop, self).flowTo(drain)
                drain.flowStopped(ZeroDivisionError())
                return result

        @tube
        class OneAndTwo(object):
            def started(self):
                yield 1
            def stopped(self, reason):
                yield 2

        ff = JustStop()
        ff.flowTo(series(OneAndTwo())).flowTo(self.fd)
        self.assertEqual(self.fd.received, [1, 2])
        self.assertEqual(len(self.fd.stopped), 1)


    def test_seriesStartsWithSeries(self):
        """
        If L{series} is called with the result of L{series} as its first
        argument, then L{series}' second argument will receive values from the
        last of the arguments to the first call to L{series}.
        """
        @tube
        class Blub(object):
            def received(self, datum):
                yield "Blub"
                yield datum

        @tube
        class Glub(object):
            def received(self, datum):
                yield "Glub"
                yield datum

        partially = series(Blub(), Glub())
        self.ff.flowTo(series(partially, self.fd))
        self.ff.drain.receive("hello")
        self.assertEqual(self.fd.received, ["Glub", "Blub", "Glub", "hello"])


    def test_seriesEndsInTerminalDrain(self):
        """
        If L{series} is called with an L{IDrain} which returns L{None} from
        C{flowingFrom}, then the return value from L{series} will return
        L{None} from its L{flowingFrom}.
        """
        terminalSeries = series(PassthruTube(), self.fd)
        self.assertIdentical(self.ff.flowTo(terminalSeries), None)



class ErrorBehaviorTests(TestCase):
    """
    Test cases for when unexpected exceptions are raised.
    """

    def test_startedRaises(self):
        """
        If L{ITube.started} raises an exception, the exception will be logged,
        the tube's fount will have L{IFount.stopFlow} called, and
        L{IDrain.flowStopped} will be called on the tube's downstream drain.
        """
        @tube
        class UnstartableTube(object):
            def started(self):
                raise ZeroDivisionError

        ff = FakeFount()
        fd = FakeDrain()
        siphonDrain = series(UnstartableTube(), fd)
        ff.flowTo(siphonDrain)
        errors = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEquals(len(errors), 1)
        self.assertEquals(ff.flowIsStopped, True)
        self.assertEquals(fd.stopped[0].type, ZeroDivisionError)


    def test_startedRaisesNoDrain(self):
        """
        If L{ITube.started} raises an exception, the exception will be logged,
        the tube's fount will have L{IFount.stopFlow} called, and
        L{IDrain.flowStopped} will be called on the tube's downstream drain.
        """
        @tube
        class UnstartableTube(object):
            def started(self):
                raise ZeroDivisionError

        ff = FakeFount()
        siphonDrain = series(UnstartableTube())
        ff.flowTo(siphonDrain)
        errors = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEquals(len(errors), 1)
        self.assertEquals(ff.flowIsStopped, True)



class TodoTests(TestCase):
    """
    Todo'd tests that should all be fixed and deleted soon, mostly for error
    handling.
    """

    todo = "not just yet"

    def test_receivedRaises(self):
        """
        If L{ITube.received} raises an exception, the exception will be logged,
        and...
        """
        self.fail()


    def test_stoppedRaises(self):
        """
        If L{ITube.stopped} raises an exception, the exception will be logged,
        and...
        """
        self.fail()


    def test_iterOnResultRaises(self):
        """
        When the iterator returned from L{ITube}.
        """
        self.fail()


    def test_nextOnIteratorRaises(self):
        """
        If L{next} on the iterator returned from L{ITube.started} (OR OTHER)
        raises an exception, the exception will be logged, and...
        """
        self.fail()


    def test_deferredFromNextOnIteratorFails(self):
        """
        If L{next} on the iterator returned from L{ITube.started} (OR OTHER)
        returns a L{Deferred} which then fails, the failure will be logged,
        and...
        """
        self.fail()


    def test_reassembleRaises(self):
        """
        If L{IDivertable.reassemble} raises an exception, then...
        """
        self.fail()


