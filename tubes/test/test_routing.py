# -*- test-case-name: tubes.test.test_routing -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.routing}.
"""

from __future__ import print_function

from twisted.trial.unittest import SynchronousTestCase as TestCase

from ..tube import tube, series
from ..routing import Router

from ..test.util import (FakeFount, FakeDrain)


@tube
class IntStarter(object):
    """
    A tube that yields an integer.
    """
    def __init__(self, i):
        self.i = i
    def started(self):
        """
        Yield an integer.
        """
        yield self.i

def isEven(n):
    if n % 2 == 0:
        return True
    else:
        return False

class TestIntRouter(TestCase):
    """
    Tests for L{Router}.
    """
    def setUp(self):
        self.ff = FakeFount()
        self.evenDrain = FakeDrain()
        self.oddDrain = FakeDrain()

        self.router = Router(isEven)
        self.oddFount = self.router.newRoute(False)
        self.evenFount = self.router.newRoute(True)
        self.oddFount.flowTo(self.oddDrain)
        self.evenFount.flowTo(self.evenDrain)

    def test_odd(self):
        """
        Test that the router can successfully route odd numbers.
        """
        self.ff.flowTo(series(IntStarter(667), self.router.drain))
        self.assertEquals(self.oddDrain.received, [667])
        self.assertEquals(self.evenDrain.received, [])

    def test_even(self):
        """
        Test that the router can successfully route even numbers.
        """
        self.ff.flowTo(series(IntStarter(668), self.router.drain))
        self.assertEquals(self.evenDrain.received, [668])
        self.assertEquals(self.oddDrain.received, [])
