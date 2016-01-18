# -*- test-case-name: tubes.test.test_routing -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A L{Router} receives items with addressing information and dispatches them to
an appropriate output, stripping the addressing information off.

Use like so::

    from tubes.tube import receiver, series
    from tubes.routing import Router, to

    aRouter = Router()
    evens = aRouter.newRoute()
    odds = aRouter.newRoute()

    @receiver()
    def evenOdd(item):
        if (item % 2) == 0:
            yield to(evens, item)
        else:
            yield to(odds, item)

    numbers.flowTo(series(evenOdd, aRouter.drain))

Assuming C{numbers} is a fount of counting integers, this creates two founts:
C{evens} and C{odds}, whose outputs are even and odd integers, respectively.
Note that C{evenOdd} also uses C{evens} and C{odds} as I{addresses}; the first
argument to L{to} says I{where} the value will go.

Why do this rather than just having C{evenOdd} just call methods directly based
on whether a number is even or odd?

By using a L{Router}, flow control relationships are automatically preserved by
the same mechanism that tubes usually use.  The distinct drains of C{evens} and
C{odds} can both independently pause their founts, and the pause state will be
propagated to the "numbers" fount.  If you want to send on outputs to multiple
drains which may have complex flow-control interrelationships, you can't do
that by calling the C{receive} method directly since any one of those methods
might reentrantly pause its fount.
"""

from zope.interface import implementer

from .tube import receiver, series
from .itube import IDrain
from .fan import Out
from .kit import beginFlowingFrom

if 0:
    from zope.interface.interfaces import ISpecification
    ISpecification

__all__ = [
    "Router",
    "Routed",
    "to",
]


class Routed(object):
    """
    A L{Routed} is a specification describing another specification that has
    been wrapped in a C{to}.  As such, it is an incomplete implementation of
    L{ISpecification}.
    """

    def __init__(self, specification=None):
        """
        Derive a L{Routed} version of C{specification}.

        @param specification: the specification that will be provided by the
            C{what} attribute of providers of this specification.
        @type specification: L{ISpecification}
        """
        self.specification = specification


    def isOrExtends(self, other):
        """
        Is this L{Routed} substitutable for the given specification?

        @param other: Another L{Routed} or specification.
        @type other: L{ISpecification}

        @return: L{True} if so, L{False} if not.
        """
        if not isinstance(other, Routed):
            return False
        if self.specification is None or other.specification is None:
            return True
        return self.specification.isOrExtends(other.specification)


    def providedBy(self, instance):
        """
        Is this L{Routed} provided by a particular value?

        @param instance: an object which may or may not provide this
            specification.
        @type instance: L{object}

        @return: L{True} if so, L{False} if not.
        @rtype: L{bool}
        """
        if not isinstance(instance, _To):
            return False
        if self.specification is None:
            return True
        return self.specification.providedBy(instance._what)


    def __eq__(self, other):
        """
        Routed(X) compares equal to Routed(X).
        """
        if not isinstance(other, Routed):
            return NotImplemented
        return self.specification == other.specification


    def __ne__(self, other):
        """
        Routed(X) compares unequal to Routed(Y).
        """
        if not isinstance(other, Routed):
            return NotImplemented
        return self.specification != other.specification



class _To(object):
    """
    An object destined for a specific destination.
    """

    def __init__(self, where, what):
        """
        Create a L{_To} to a particular route with a given value.

        @param _where: see L{to}

        @param _what: see L{to}
        """
        self._where = where
        self._what = what


    def __repr__(self):
        """
        @return: an explanatory string.
        """
        return "to({!r}, {!r})".format(self._where, self._what)



def to(where, what):
    """
    Construct a provider of L{Routed}C{(providedBy(where))}.

    @see: L{tubes.routing}

    @param where: A fount returned from L{Router.newRoute}.  This must be
        I{exactly} the return value of L{Router.newRoute}, as it is compared by
        object identity and not by any feature of L{IFount}.

    @param what: the value to deliver.

    @return: a L{Routed} object.
    """
    return _To(where, what)



class Router(object):
    """
    A drain with multiple founts that consumes L{Routed}C{(IX)} from its input
    and produces C{IX} to its outputs.

    @ivar _out: A fan-out that consumes L{Routed}C{(X)} and produces C{X}.
    @type _out: L{Out}

    @ivar drain: The input to this L{Router}.
    @type drain: L{IDrain}
    """

    def __init__(self, outputType=None):
        self._out = Out()
        self._outputType = outputType
        @implementer(IDrain)
        class NullDrain(object):
            inputType = outputType
            fount = None
            def flowingFrom(self, fount):
                beginFlowingFrom(self, fount)
            def receive(self, item):
                pass
            def flowStopped(self, reason):
                pass
        self.newRoute("NULL").flowTo(NullDrain())
        self.drain = self._out.drain


    def newRoute(self, name=None):
        """
        Create a new route.

        A route has two uses; first, it is an L{IFount} that you can flow to a
        drain.

        Second, it is the "where" parameter passed to L{to}.  Each value sent
        to L{Router.drain} should be a L{to} constructed with a value returned
        from this method as the "where" parameter.

        @param name: Give the route a name for debugging purposes.
        @type name: native L{str}

        @return: L{IFount}
        """
        @receiver(inputType=Routed(self._outputType),
                  outputType=self._outputType,
                  name=name)
        def received(item):
            if not isinstance(item, _To):
                raise TypeError("{0} is not routed".format(item))
            if item._where is fount:
                yield item._what
        fount = self._out.newFount().flowTo(series(received))
        return fount
