# -*- test-case-name: tubes.test.test_fan -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A L{Router} receives items with addressing information and dispatches them to
an appropriate output, stripping the addressing information off.

Use like so::

    from tubes.routing import Router, Routed, to

    aRouter = Router(int)

    evens, evenFount = aRouter.newRoute()
    odds, oddFount = aRouter.newRoute()

    @tube
    class EvenOdd(object):
        outputType = Routed(int)
        def received(self, item):
            if (item % 2) == 0:
                yield to(evens, item)
            else:
                yield to(odds, item)

    numbers.flowTo(aRouter)

This creates a fount in evenFount and oddFount, which each have an outputType
of "int".

Why do this rather than just having C{EvenOdd} just call methods directly based
on whether a number is even or odd?

By using a L{Router}, flow control relationships are automatically preserved by
the same mechanism that tubes usually use.  The distinct drains of evenFount
and oddFount can both be independently paused, and the pause state will be
propagated to the "numbers" fount.  If you want to send on outputs to multiple
drains which may have complex flow-control interrelationships, you can't do
that by calling the C{receive} method directly since any one of those methods
might reentrantly pause you.
"""

from .tube import tube, receiver
from .fan import Out


class Routed(object):
    """
    A L{Routed} is an interface describing another interface that has been
    wrapped in a C{to}.  As such, it is an incomplete implementation of
    L{zope.interface.interfaces.IInterface}.
    """

    def __init__(self, interface=None):
        """
        Derive a L{Routed} version of C{interface}.

        @param interface: the interface that will be provided by the C{what}
            attribute of providers of this interface.
        @type interface: L{zope.interface.interfaces.IInterface}
        """
        self.interface = interface


    def isOrExtends(self, other):
        """
        Is this L{Routed} substitutable for the given specification?

        @param other: Another L{Routed} or interface.
        @type other: L{zope.interface.interfaces.IInterface}

        @return: L{True} if so, L{False} if not.
        """
        if not isinstance(other, Routed):
            return False
        if self.interface is None or other.interface is None:
            return True
        return self.interface.isOrExtends(other.interface)


    def providedBy(self, instance):
        """
        Is this L{Routed} provided by a particular value?

        @param instance: an object which may or may not provide this interface.
        @type instance: L{object}

        @return: L{True} if so, L{False} if not.
        @rtype: L{bool}
        """
        if not isinstance(instance, _To):
            return False
        if self.interface is None:
            return True
        return self.interface.providedBy(instance._what)



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



@tube
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
        self.drain = self._out.drain


    def newRoute(self):
        """
        Create a new route.

        A route has two uses; first, it is an L{IFount} that you can flow to a
        drain.

        Second, it is the "where" parameter passed to L{to}.  Each value sent
        to L{Router.drain} should be a L{to} constructed with a value returned
        from this method as the "where" parameter.

        @return: L{IFount}
        """
        @receiver(inputType=Routed(self._outputType),
                  outputType=self._outputType)
        def received(item):
            if isinstance(item, to):
                if item._where is fount:
                    yield item._what
        fount = self._out.newFount().flowTo(received)
        return fount
