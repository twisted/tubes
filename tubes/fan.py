# -*- test-case-name: tubes.test.test_fan -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tools for turning L{founts <IFount>} and L{drains <IDrain>} into multiple
founts and drains.
"""

from itertools import count

from zope.interface import implementer

from twisted.python.components import proxyForInterface

from .kit import Pauser, beginFlowingTo, beginFlowingFrom, OncePause
from .itube import IDrain, IFount


@implementer(IDrain)
class _InDrain(object):
    """
    The one of the drains associated with an fan.L{In}.
    """

    inputType = None

    fount = None

    def __init__(self, fanIn):
        """
        Create an L{_InDrain} with an L{In}.
        """
        self._in = fanIn
        self._presentPause = None


    def flowingFrom(self, fount):
        """
        The attached L{In} is now receiving inputs from the given fount.

        @param fount: Any fount.

        @return: C{None}; this is a terminal drain and not a data-processing
            drain.
        """
        beginFlowingFrom(self, fount)
        if self._in.fount._isPaused:
            self._presentPause = fount.pauseFlow()
        return None


    def receive(self, item):
        """
        Pass along any received item to the drain that the L{In}'s fount is
        flowing to.

        @param item: any object

        @return: passed through from the active drain.
        """
        return self._in.fount.drain.receive(item)


    def flowStopped(self, reason):
        """
        Remove this drain from its attached L{In}.

        @param reason: the reason the flow stopped.
        """
        self._in._drains.remove(self)



@implementer(IFount)
class _InFount(object):
    """
    An L{_InFount} is the single fount associated with an L{In}.
    """

    outputType = None

    drain = None

    def __init__(self, fanIn):
        """
        Create an L{_InFount} with an L{In}.
        """
        self._in = fanIn
        self._isPaused = False
        def doPause():
            self._isPaused = True
            for drain in self._in._drains:
                drain._presentPause = drain.fount.pauseFlow()
        def doResume():
            self._isPaused = False
            for drain in self._in._drains:
                drain._presentPause.unpause()
        self._pauser = Pauser(doPause, doResume)
        self._pauseBecauseNoDrain = OncePause(self._pauser)
        self._pauseBecauseNoDrain.pauseOnce()


    def flowTo(self, drain):
        """
        Start flowing to the given C{drain}.

        @param drain: the drain to deliver all inputs from all founts attached
            to the underlying L{In}.

        @return: the fount downstream of C{drain}.
        """
        result = beginFlowingTo(self, drain)
        # TODO: if drain is not None
        if self.drain is None:
            self._pauseBecauseNoDrain.pauseOnce()
        else:
            self._pauseBecauseNoDrain.maybeUnpause()
        return result


    def pauseFlow(self):
        """
        Pause the flow of all founts flowing into L{_InDrain}s for this L{In}.

        @return: A pause which pauses all upstream founts.
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        Stop the flow of all founts flowing into L{_InDrain}s for this L{In}.
        """
        for drain in self._in._drains:
            drain.fount.stopFlow()



class In(object):
    r"""
    A fan.L{In} presents a single L{fount <IFount>} that delivers the inputs
    from multiple L{drains <IDrain>}::

        your fount ---> In.newDrain()--\
                                        \
        your fount ---> In.newDrain()----> In ---> In.fount ---> your drain
                                        /
        your fount ---> In.newDrain()--/

    @ivar fount: The fount which produces all new attributes.
    @type fount: L{IFount}
    """
    def __init__(self):
        self._drains = []
        self.fount = _InFount(self)


    def newDrain(self):
        """
        Create a new L{drains <IDrain>} which will send its
        inputs out via C{self.fount}.

        @return: a drain.
        """
        it = _InDrain(self)
        self._drains.append(it)
        return it



@implementer(IFount)
class _OutFount(object):
    """
    The concrete fount type returned by L{Out.newFount}.
    """
    drain = None

    outputType = None

    def __init__(self, upstreamPauser, stopper):
        """
        @param upstreamPauser: A L{Pauser} which will pause the upstream fount
            flowing into our L{Out}.

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
class _OutDrain(object):
    """
    An L{_OutDrain} is the single L{IDrain} associated with an L{Out}.
    """

    fount = None

    def __init__(self, founts):
        """
        Construct an L{_OutDrain} with a collection of founts, an input type
        and an output type.

        @param founts: the founts whose drains we should flow to.
        @type founts: L{list} of L{IFount}
        """
        self._pause = None
        self._paused = False

        self._founts = founts

        def _actuallyPause():
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
        for fount in self._founts:
            if fount.drain is not None:
                return fount.drain.inputType


    def flowingFrom(self, fount):
        """
        The L{Out} associated with this L{_OutDrain} is now receiving inputs
        from the given fount.

        @param fount: the new source of input for all drains attached to this
            L{Out}.

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
        beginFlowingFrom(self, fount)


    def receive(self, item):
        """
        Deliver an item to each L{IDrain} attached to the L{Out} via
        C{Out().newFount().flowTo(...)}.

        @param item: any object
        """
        for fount in self._founts[:]:
            fount._deliverOne(item)


    def flowStopped(self, reason):
        """
        Deliver an item to each L{IDrain} attached to the L{Out} via
        C{Out().newFount().flowTo(...)}.

        @param reason: the reason that the flow stopped.
        """
        for fount in self._founts[:]:
            if fount.drain is not None:
                fount.drain.flowStopped(reason)



class Out(object):
    r"""
    A fan.L{Out} presents a single L{drain <IDrain>} that delivers the inputs
    to multiple L{founts <IFount>}::

                                           /--> Out.newFount() --> your drain
                                          /
        your fount --> Out.drain --> Out <----> Out.newFount() --> your drain
                                          \
                                           \--> Out.newFount() --> your drain

    @ivar drain: The fount which produces all new attributes.
    @type drain: L{IDrain}
    """

    def __init__(self):
        """
        Create an L{Out}.
        """
        self._founts = []
        self.drain = _OutDrain(self._founts)


    def newFount(self):
        """
        Create a new L{IFount} whose drain will receive inputs from this
        L{Out}.

        @return: a fount associated with this fan-L{Out}.
        @rtype: L{IFount}.
        """
        f = _OutFount(self.drain._pauser, self._founts.remove)
        self._founts.append(f)
        return f



class Thru(proxyForInterface(IDrain, "_outDrain")):
    r"""
    A fan.L{Thru} takes an input and fans it I{thru} multiple
    drains-which-produce-founts, such as L{tubes <tubes.itube.ITube>}::

                Your Fount
             (producing "foo")
                    |
                    v
                  Thru
                    |
                  _/|\_
                _/  |  \_
               /    |    \
        foo2bar  foo2baz  foo2qux
               \_   |   _/
                 \_ | _/
                   \|/
                    |
                    v
                  Thru
                    |
                    v
                Your Drain
         (receiving a combination
             of foo, bar, baz)

    The way you would construct such a flow in code would be::

        yourFount.flowTo(Thru([series(foo2bar()),
                               series(foo2baz()),
                               series(foo2qux())])).flowTo(yourDrain)
    """

    def __init__(self, drains):
        """
        Create a L{Thru} with an iterable of L{IDrain}.

        All of the drains in C{drains} should be drains that produce a new
        L{IFount} from L{flowingFrom <IDrain.flowingFrom>}, which means they
        should be a L{series <tubes.tube.series>} of L{tubes
        <tubes.itube.ITube>}, or drains that behave like that, such as L{Thru}
        itself.

        @param drain: an iterable of L{IDrain}
        """
        self._in = In()
        self._out = Out()

        self._drains = list(drains)
        self._founts = list(None for drain in self._drains)
        self._outFounts = list(self._out.newFount() for drain in self._drains)
        self._inDrains = list(self._in.newDrain() for drain in self._drains)
        self._outDrain = self._out.drain


    def flowingFrom(self, fount):
        """
        Accept input from C{fount} and produce output filtered by all of the
        C{drain}s given to this L{Thru}'s constructor.

        @param fount: a fount whose outputs should flow through our series of
            transformations.

        @return: an output fount which aggregates all the values produced by
            the drains given to this L{Thru}'s constructor.
        """
        super(Thru, self).flowingFrom(fount)
        for idx, appDrain, outFount, inDrain in zip(
                count(), self._drains, self._outFounts, self._inDrains):
            appFount = outFount.flowTo(appDrain)
            if appFount is None:
                appFount = self._founts[idx]
            else:
                self._founts[idx] = appFount
            appFount.flowTo(inDrain)
        nextFount = self._in.fount

        # Literally copy/pasted from _SiphonDrain.flowingFrom.  Hmm.
        nextDrain = nextFount.drain
        if nextDrain is None:
            return nextFount
        return nextFount.flowTo(nextDrain)

