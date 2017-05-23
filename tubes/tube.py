# -*- test-case-name: tubes.test.test_tube -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
See L{tube}.
"""

from __future__ import print_function

from zope.interface import implementer
from zope.interface.verify import verifyClass

from twisted.python.components import proxyForInterface
from twisted.python.failure import Failure

from .itube import IDrain, ITube, IDivertable, IFount, StopFlowCalled
from ._siphon import _tubeRegistry, _Siphon, skip
from ._components import _registryActive
from .kit import NoPause as _PlaceholderPause

__all__ = [
    "Diverter",
    "receiver",
    "tube",
    "skip"
]



def tube(cls):
    """
    L{tube} is a class decorator which declares a given class to be an
    implementer of L{ITube} and fills out any methods or attributes which are
    not present on the decorated type with null-implementation methods (those
    which return None) and None attributes.

    @param cls: A class with some or all of the attributes or methods described
        by L{ITube}.
    @type cls: L{type}

    @return: C{cls}
    @rtype: L{type} which implements L{ITube}
    """

    # This is better than a superclass, because:

    # - you can't do a separate 'isinstance(Tube)' check instead of
    #   ITube.providedBy like you're supposed to

    # - you can't just instantiate Tube directly, that is pointless
    #   functionality so we're not providing it

    # - it avoids propagating a bad example that other codebases will copy to
    #   depth:infinity, rather than depth:1 where subclassing is actually sort
    #   of okay

    # - it provides a more straightforward and reliable mechanism for
    #   future-proofing code.  If you're inheriting from a superclass and you
    #   want it to do something to warn users, upgrade an interface, and so on,
    #   you have to try to cram a new meta-type into the user's hierarchy so a
    #   function gets invoked at the right time.  If you're invoking this class
    #   decorator, then it just gets invoked like a normal function, and we can
    #   put some code in here that examines the type and does whatever it wants
    #   to do, because the @ syntax simply called it as a function.

    # It still shares some issues with inheritance, such as:

    # - the direction of visibility within the hierarchy is still wrong.  you
    #   can still do 'self.someMethodIDidntImplement()' and get a result.

    # - it destructively modifies the original class, so what you see isn't
    #   quite what you get.  a cleaner compositional approach would simply wrap
    #   an object around another object (but that would mean inventing a new
    #   incompletely-specified type that floats around at runtime, rather than
    #   a utility to help you completely implement ITube at import time)

    def started(self):
        """
        A null implementation of started.

        @param self: An instance of the C{tube} being defined.
        """

    def stopped(self, reason):
        """
        A null implementation of stopped.

        @param self: An instance of the C{tube} being defined.

        @param reason: see L{ITube}
        """

    def received(self, item):
        """
        A null implementation of received.

        @param self: An instance of the C{tube} being defined.

        @param item: see L{ITube}
        """

    fillers = [('started', started),
               ('stopped', stopped),
               ('received', received),
               ('inputType', None),
               ('outputType', None)]

    notHere = object()

    for name, value in fillers:
        if getattr(cls, name, notHere) is notHere:
            setattr(cls, name, value)

    cls = implementer(ITube)(cls)
    verifyClass(ITube, cls)
    return cls



@implementer(ITube)
class _Tubule(object):
    """
    A tube created for the C{@tube} decorator.
    """
    def __init__(self, inputType, outputType, received, name):
        """
        @param inputType: An interface for the input type.

        @param outputType: an interface for the output type.

        @param received: a callable to implement C{received}.

        @param name: a string describing this L{_Tubule}.
        """
        self.inputType = inputType
        self.outputType = outputType
        self.received = received
        self._name = name


    def started(self):
        """
        Tubules cannot produce a greeting.

        @return: an empty iterable.
        """
        return ()


    def stopped(self, reason):
        """
        Tubules cannot produce a farewell.

        @param reason: the reason the flow stopped.

        @return: an empty iterable.
        """
        return ()


    def __repr__(self):
        """
        @return: this L{_Tubule}'s name.
        """
        return self._name



def receiver(inputType=None, outputType=None, name=None):
    """
    Decorator for a stateless function which receives inputs.

    For example, to add 1 to each in a stream of numbers::

        @receiver(inputType=int, outputType=int)
        def addOne(item):
            yield item + 1

    @param inputType: The C{inputType} attribute of the resulting L{ITube}.

    @param outputType: The C{outputType} attribute of the resulting L{ITube}.

    @param name: a name describing the tubule for it to show as in a C{repr}.
    @type name: native L{str}

    @return: a stateless tube with the decorated method as its C{received}
        method.
    @rtype: L{ITube}
    """
    def decorator(decoratee):
        return _Tubule(inputType, outputType, decoratee,
                       name if name is not None else decoratee.__name__)
    return decorator



def series(start, *tubes):
    """
    Connect up a series of objects capable of transforming inputs to outputs;
    convert a sequence of L{ITube} objects into a sequence of connected
    L{IFount} and L{IDrain} objects.  This is necessary to be able to C{flowTo}
    an object implementing L{ITube}.

    This function can best be understood by understanding that::

        x = a
        a.flowTo(b).flowTo(c)

    is roughly analagous to::

        x = series(a, b, c)

    with the additional feature that C{series} will convert C{a}, C{b}, and
    C{c} to the requisite L{IDrain} objects first.

    @param start: The initial element in the chain; the object that will
        consume inputs passed to the result of this call to C{series}.
    @type start: an L{ITube}, or anything adaptable to L{IDrain}.

    @param tubes: Each element of C{plumbing}.
    @type tubes: a L{tuple} of L{ITube}s or objects adaptable to L{IDrain}.

    @return: An L{IDrain} that can consume inputs of C{start}'s C{inputType},
        and whose C{flowingFrom} will return an L{IFount} that will produce
        outputs of C{plumbing[-1]} (or C{start}, if plumbing is empty).
    @rtype: L{IDrain}

    @raise TypeError: if C{start}, or any element of C{plumbing} is not
        adaptable to L{IDrain}.
    """
    with _registryActive(_tubeRegistry):
        result = IDrain(start)
        currentFount = result.flowingFrom(None)
        drains = [IDrain(tube) for tube in tubes]
    for drain in drains:
        currentFount = currentFount.flowTo(drain)
    return result



@tube
class _DrainingTube(object):
    """
    A L{_DrainingTube} is an L{ITube} that unbuffers a list of items.  It is an
    implementation detail of the way that L{Diverter} works.
    """

    def __init__(self, items, eventualUpstream, eventualDownstream):
        """
        Create a L{_DrainingTube} with some C{items} to drain, a L{drain
        <IDrain>} to drain them to, and a L{fount <IFount>} to flow to that
        C{drain} once the items are flowed.

        @param items: An iterable of items to drain.
        @type items: iterable

        @param eventualUpstream: a L{fount <IFount>} which should flow to
            C{eventualDownstream} once the last item in C{items} has been
            passed on.

        @param eventualDownstream: a L{drain <IDrain>} which should receive
            each item in C{items} and then accept the flow from
            C{eventualUpstream}.
        """
        self._items = list(items)
        self._eventualUpstream = eventualUpstream
        self._eventualDownstream = eventualDownstream


    def __repr__(self):
        """
        Display the remaining items to be drained.
        """
        return ("<Draining Tube {0}>".format(repr(self._items)))


    def started(self):
        """
        Yield each item from the C{items} passed to the constructor, then
        switch flow to C{_eventualUpstream}.
        """
        while self._items:
            item = self._items.pop(0)
            yield item
        self._eventualUpstream.flowTo(self._eventualDownstream)



@implementer(IFount)
class _NullFount(object):
    """
    An I{almost} no-op implementation of fount which does nothing but update
    its C{drain} to point at itself.
    """

    outputType = None
    drain = None

    def flowTo(self, drain):
        """
        Update the C{drain} attribute of this L{_NullFount} and call
        C{flowingFrom} on the given C{drain}.

        @param drain: see L{IFount}

        @return: see L{IFount}
        """
        self.drain = drain
        return drain.flowingFrom(self)


    def pauseFlow(self):
        """
        Return an L{IPause} which does nothing, and then does nothing when
        resumed.

        @return: see L{IFount}
        """
        return _PlaceholderPause()


    def stopFlow(self):
        """
        Do nothing.
        """
        self.drain.flowStopped(Failure(StopFlowCalled()))



class Diverter(proxyForInterface(IDrain, "_drain")):
    """
    A L{Diverter} is a L{drain <IDrain>} which maintains a buffer of items not
    yet received by its L{IDivertable} down-stream drain.
    """

    def __init__(self, divertable):
        """
        Create a L{Diverter}.

        @param divertable: Divert a divertable.
        @type divertable: L{IDivertable} provider
        """
        if not IDivertable.providedBy(divertable):
            raise TypeError("Diverter can only wrap IDivertable providers.")
        self._divertable = divertable
        self._friendSiphon = _Siphon(divertable)
        self._drain = self._friendSiphon._tdrain


    def __repr__(self):
        """
        Nice string representation for this Diverter which mentions what it is
        diverting.
        """
        return "<Diverter for {0}>".format(self._divertable)


    def divert(self, drain):
        """
        Divert the flow from the fount which is flowing I{into this diverter}
        to instead flow into I{the given drain}, reassembling any buffered
        output from this siphon's tube first.

        @param drain: The L{drain <IDrain>} to divert the flow I{to}.
        @type drain: L{IDrain}

        @return: L{None}
        """
        unpending = self._friendSiphon.ejectPending()

        pendingPending = self._divertable.reassemble(unpending) or []
        upstream = self._friendSiphon._tdrain.fount
        nullFount = _NullFount()
        dt = series(_DrainingTube(pendingPending, upstream, drain))
        again = nullFount.flowTo(dt)
        again.flowTo(drain)
