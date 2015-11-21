# -*- test-case-name: tubes.test.test_routing -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.routing}.
"""

from unittest import TestCase

from ..routing import Router, to
from ..tube import series, receiver
from .util import FakeFount, FakeDrain

if 0:
    # Names used by PyDoctor.
    from ..itube import IFount
    IFount



class RoutingTests(TestCase):
    """
    Tests for routing.
    """

    def test_twoRoutes(self):
        """
        The L{IFount} feeding into a L{Router} may yield L{to} each route
        returned from L{Router.newRoute}.
        """
        @receiver()
        def chooser(item):
            if item % 2:
                yield to(odd, item)
            else:
                yield to(even, item)
        router = Router()
        even = router.newRoute()
        evens = FakeDrain()
        even.flowTo(evens)
        odd = router.newRoute()
        odds = FakeDrain()
        odd.flowTo(odds)
        ff = FakeFount()
        routeDrain = series(chooser, router.drain)
        ff.flowTo(routeDrain)
        for x in range(10):
            ff.drain.receive(x)
        self.assertEqual(odds.received, [1, 3, 5, 7, 9])
        self.assertEqual(evens.received, [0, 2, 4, 6, 8])


    def test_routeRepr(self):
        """
        It's useful to C{repr} a route for debugging purposes; if we give it a
        name, its C{repr} will contain that name.
        """
        router = Router()
        route = router.newRoute("hello")
        self.assertIn("hello", repr(route))

