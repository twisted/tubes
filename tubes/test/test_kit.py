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

class PauserTests(TestCase):
    """
    Tests for L{Pauser}, helper for someone who wants to implement a thing
    that pauses.
    """

    def test_pauseOnce(self):
        """
        One call to L{_Pauser.pause} will call the actuallyPause callable.
        """
        def pause():
            pause.d += 1
        pause.d = 0
        pauser = Pauser(pause, None)
        result = pauser.pause()
        self.assertTrue(verifyObject(IPause, result))
        self.assertEqual(pause.d, 1)


    def test_pauseThenUnpause(self):
        """
        A call to L{_Pauser.pause} followed by a call to the result's
        C{unpause} will call the C{actuallyResume} callable.
        """
        def pause():
            pause.d += 1
        pause.d = 0
        def resume():
            resume.d += 1
        resume.d = 0
        pauser = Pauser(pause, resume)
        pauser.pause().unpause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 1)


    def test_secondUnpauseFails(self):
        """
        The second of two consectuive calls to L{IPause.unpause} results in an
        L{AlreadyUnpaused} exception.
        """
        def pause():
            pass
        def resume():
            resume.d += 1
        resume.d = 0
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
        def pause():
            pause.d += 1
        pause.d = 0
        def resume():
            resume.d += 1
        resume.d = 0
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
        def resume():
            resume.d += 1
        resume.d = 0
        pauser = Pauser(pause, resume)
        pauser.pause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 0)
