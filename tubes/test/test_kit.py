# -*- test-case-name: tubes.test.test_kit -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.kit}.
"""

from zope.interface.verify import verifyObject

from twisted.trial.unittest import SynchronousTestCase as TestCase

from ..itube import IPause, AlreadyUnpaused
from ..kit import Pauser

def countingCallable():
    """
    Generate a callable for testing.

    @return: a callable with a C{d} attribute that indicates the number of
        times it's been called.
    """
    def callee():
        callee.d += 1
    callee.d = 0
    return callee



class PauserTests(TestCase):
    """
    Tests for L{Pauser}, helper for someone who wants to implement a thing
    that pauses.
    """

    def test_pauseOnce(self):
        """
        One call to L{_Pauser.pause} will call the actuallyPause callable.
        """
        pause = countingCallable()
        pauser = Pauser(pause, None)
        result = pauser.pause()
        self.assertTrue(verifyObject(IPause, result))
        self.assertEqual(pause.d, 1)


    def test_pauseThenUnpause(self):
        """
        A call to L{_Pauser.pause} followed by a call to the result's
        C{unpause} will call the C{actuallyResume} callable.
        """
        pause = countingCallable()
        resume = countingCallable()
        pauser = Pauser(pause, resume)
        pauser.pause().unpause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 1)


    def test_secondUnpauseFails(self):
        """
        The second of two consectuive calls to L{IPause.unpause} results in an
        L{AlreadyUnpaused} exception.
        """
        pause = countingCallable()
        resume = countingCallable()
        pauser = Pauser(pause, resume)
        aPause = pauser.pause()
        aPause.unpause()
        self.assertRaises(AlreadyUnpaused, aPause.unpause)
        self.assertEqual(resume.d, 1)


    def test_repeatedlyPause(self):
        """
        Multiple calls to L{_Pauser.pause} where not all of the pausers are
        unpaused do not result in any calls to C{actuallyResume}.
        """
        pause = countingCallable()
        resume = countingCallable()
        pauser = Pauser(pause, resume)
        one = pauser.pause()
        two = pauser.pause()
        three = pauser.pause()
        four = pauser.pause()

        one.unpause()
        two.unpause()
        three.unpause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 0)
        four.unpause()
        self.assertEqual(resume.d, 1)


    def test_reentrantPause(self):
        """
        A L{Pauser} that pauses re-entrantly will only result in one call to
        the specified C{pause} callable.
        """
        def pause():
            pause.d += 1
            pauser.pause()
        pause.d = 0
        resume = countingCallable()
        pauser = Pauser(pause, resume)
        pauser.pause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 0)


    def test_reentrantResume(self):
        """
        A L{Pauser} that resumes re-entrantly will raise L{AlreadyUnpaused}.
        """
        pause = countingCallable()
        def resume():
            resume.d += 1
            self.assertRaises(AlreadyUnpaused, anPause.unpause)
        resume.d = 0
        pauser = Pauser(pause, resume)
        anPause = pauser.pause()
        anPause.unpause()
        anotherPause = pauser.pause()
        self.assertEqual(resume.d, 1)
        self.assertEqual(pause.d, 2)
        anotherPause.unpause()
        self.assertEqual(resume.d, 2)
