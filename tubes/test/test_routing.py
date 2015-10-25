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
class Starter(object):
    """
    A tube that yields an integer.
    """

    def started(self):
        """
        Yield an integer.
        """
        yield 667

def isEven(n):
    if n % 2 == 0:
        return True
    else:
        return False

class TestBasicRouter(TestCase):
    """
    Tests for L{Router}.
    """

    def setUp(self):
        self.ff = FakeFount()
        self.fd = FakeDrain()
        
    def test_basic_int_router(self):
        aRouter = Router(isEven)
        oddFount = aRouter.newRoute(False)        
        oddFount.flowTo(self.fd)
        self.ff.flowTo(series(Starter(), aRouter.drain))
        self.assertEquals(self.fd.received, [667])
