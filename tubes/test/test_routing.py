# -*- test-case-name: tubes.test.test_routing -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.routing}.
"""

from unittest import TestCase

from ..routing import Router, to, Routed
from ..tube import series, receiver
from .util import FakeFount, FakeDrain, IFakeOutput, IFakeInput, FakeInput

if 0:
    # Names used by PyDoctor.
    from ..itube import IFount
    IFount



class RouterTests(TestCase):
    """
    Tests for L{Router}.
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
        even = router.newRoute("even")
        evens = FakeDrain()
        even.flowTo(evens)
        odd = router.newRoute("odd")
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
        self.assertTrue("hello" in repr(route))


    def test_defaultTypeChecking(self):
        """
        L{Router}'s drain accepts only L{Routed} objects; if no other type is
        specified, L{Routed}C{(None)}.
        """
        router = Router()
        ff = FakeFount(IFakeOutput)
        self.assertEqual(router.drain.inputType, Routed(None))
        self.assertRaises(TypeError, ff.flowTo, router.drain)
        self.assertEqual(router.newRoute().outputType, None)


    def test_specifiedTypeChecking(self):
        """
        The C{outputType} argument to L{Router}'s constructor specifies the
        type of output that its routes will provide, and also the routed type
        required as an input.
        """
        router = Router(IFakeInput)
        incorrect = FakeDrain(IFakeOutput)
        correct = FakeDrain(IFakeInput)
        self.assertEqual(router.drain.inputType, Routed(IFakeInput))
        self.assertEqual(router.newRoute().outputType, IFakeInput)
        self.assertRaises(TypeError, router.newRoute().flowTo, incorrect)
        self.assertEqual(router.newRoute().flowTo(correct), None)
        correctFount = FakeFount(Routed(IFakeInput))
        incorrectFount = FakeFount(Routed(IFakeOutput))
        self.assertRaises(TypeError, incorrectFount.flowTo, router.drain)
        self.assertEquals(None, correctFount.flowTo(router.drain))



class RoutedTests(TestCase):
    """
    Tests for L{Routed}.
    """

    def test_eq(self):
        """
        C{==} on L{Routed} is L{True} for equivalent ones, L{False} otherwise.
        """
        self.assertEqual(True, Routed(IFakeInput) == Routed(IFakeInput))
        self.assertEqual(False, Routed(IFakeInput) == Routed(IFakeOutput))
        self.assertEqual(False, Routed() == 7)


    def test_ne(self):
        """
        C{==} on L{Routed} is L{False} for equivalent ones, L{True} otherwise.
        """
        self.assertEqual(False, Routed(IFakeInput) != Routed(IFakeInput))
        self.assertEqual(True, Routed(IFakeInput) != Routed(IFakeOutput))
        self.assertEqual(True, Routed() != 7)


    def test_providedBy(self):
        """
        L{Routed.providedBy} ensures that the given object is a L{to} and that
        its payload provides the proper specification.
        """
        router = Router()
        route = router.newRoute()
        self.assertEqual(False,
                         Routed(IFakeInput).providedBy(FakeInput()))
        self.assertEqual(False,
                         Routed(IFakeInput).providedBy(to(route, object())))
        self.assertEqual(True,
                         Routed(IFakeInput).providedBy(to(route, FakeInput())))


    def test_providedByNone(self):
        """
        L{Routed.providedBy} ensures that the given object is L{to} but makes
        no assertions about its payload if given L{Routed} is given no
        sub-specification.
        """
        router = Router()
        route = router.newRoute()
        self.assertEqual(False, Routed().providedBy(object()))
        self.assertEqual(True, Routed().providedBy(to(route, object())))

