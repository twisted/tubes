# -*- test-case-name: tubes.test.test_routing -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import implementer

from .kit import Pauser, beginFlowingTo
from .itube import IDrain, IFount


@implementer(IFount)
class _RouteFount(object):
    """
    The concrete fount type returned by L{Router.newRoute}.
    """
    drain = None

    outputType = None

    def __init__(self, upstreamPauser, stopper):
        """
        @param upstreamPauser: A L{Pauser} which will pause the upstream fount
            flowing into our L{Router}.

        @param stopper: A 0-argument callback to execute on
            L{IFount.stopFlow}
        """
        self._receivedWhilePaused = []
        self._myPause = None
        self._stopper = stopper

        def actuallyPause():
            self._myPause = upstreamPauser.pause()

        def actuallyUnpause():
            aPause = self._myPause
            self._myPause = None
            if self._receivedWhilePaused:
                self.drain.receive(self._receivedWhilePaused.pop(0))
            aPause.unpause()

        self._pauser = Pauser(actuallyPause, actuallyUnpause)


    def flowTo(self, drain):
        """
        Flow to the given drain.  Don't do anything special; just set up the
        drain attribute and return the appropriate value.

        @param drain: A drain to fan out values to.

        @return: the result of C{drain.flowingFrom}
        """
        return beginFlowingTo(self, drain)


    def pauseFlow(self):
        """
        Pause the flow.

        @return: a pause
        @rtype: L{IPause}
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        Invoke the callback supplied to C{__init__} for stopping.
        """
        self._stopper(self)


    def _deliverOne(self, item):
        """
        Deliver one item to this fount's drain.

        This is only invoked when the upstream is unpaused.

        @param item: An item that the upstream would like to pass on.
        """
        if self.drain is None:
            return
        if self._myPause is not None:
            self._receivedWhilePaused.append(item)
            return
        self.drain.receive(item)

@implementer(IDrain)
class _RouterDrain(object):
    """
    An L{_RouterDrain} is the single L{IDrain} associated with a L{Router}.
    """

    fount = None

    def __init__(self, router):
        """
        Construct a L{_RouterDrain}.

        @param router: the router associated with this drain
        @type founts: L{Router}
        """

        self._router = router
        self._pause = None
        self._paused = False

        def _actuallyPause():
            if self._paused:
                raise NotImplementedError()
            self._paused = True
            if self.fount is not None:
                self._pause = self.fount.pauseFlow()

        def _actuallyResume():
            p = self._pause
            self._pause = None
            self._paused = False
            if p is not None:
                p.unpause()

        self._pauser = Pauser(_actuallyPause, _actuallyResume)

    @property
    def inputType(self):
        """
        Implement the C{inputType} property by relaying it to the input type of
        the drains.
        """
        # TODO: prevent drains from different inputTypes from being added
        for fount in self._router._founts:
            if fount.drain is not None:
                return fount.drain.inputType


    def flowingFrom(self, fount):
        """
        The L{Router} associated with this L{_RouterDrain} is now receiving inputs
        from the given fount.

        @param fount: the new source of input for all drains attached to this
            L{Router}.

        @return: L{None}, as this is a terminal drain.
        """
        if self._paused:
            p = self._pause
            if fount is not None:
                self._pause = fount.pauseFlow()
            else:
                self._pause = None
            if p is not None:
                p.unpause()
        self.fount = fount

    def receive(self, item):
        """
        Deliver an item to the L{IDrain} attached to the L{RouteFount} via
        C{Router().newRoute(...).flowTo(...)}.

        @param item: any object
        """
        destination = self._router._getItemDestination(item)
        fount = self._router._routes[destination]
        fount._deliverOne(item)

    def flowStopped(self, reason):
        for fount in self._router._founts[:]:
            if fount.drain is not None:
                fount.drain.flowStopped(reason)

class Router(object):

    def __init__(self, getItemDestination):
        """
        Create an L{Router}.

        @param getItemDestination: the function that is called for each
        received message and decodes it's destination address.
        @type getItemDestination: function that takes one argument
        and returns one value
        """
        self._getItemDestination = getItemDestination
        self._routes = {} # destination -> fount
        self._founts = []
        self.drain = _RouterDrain(self)

    def newRoute(self, destination):
        """
        Create a new L{IFount} whose drain will receive items from this
        L{Router} if the message destination matches the one given.

        @return: a fount associated with this L{Router}.
        @rtype: L{IFount}.
        """
        f = _RouteFount(self.drain._pauser, self._founts.remove)
        self._founts.append(f)
        self._routes[destination] = f
        return f
