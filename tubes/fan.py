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

from .kit import Pauser, beginFlowingTo, beginFlowingFrom
from .itube import IDrain, IFount, IPause


@implementer(IDrain)
class _InDrain(object):
    """
    
    """

    inputType = None

    fount = None

    def __init__(self, fanIn):
        """
        
        """
        self._in = fanIn
        self._pauseBecauseNoDrain = None


    def flowingFrom(self, fount):
        """
        
        """
        beginFlowingFrom(self, fount)
        # Except the fount is having similar thoughts about us as a drain, and
        # this can only happen in one order or the other. right now siphon
        # takes care of it.
        self._checkNoDrainPause()
        return None


    def _checkNoDrainPause(self):
        """
        
        """
        pbnd = self._pauseBecauseNoDrain
        self._pauseBecauseNoDrain = None
        # Do this _before_ unpausing the old one; if it's a new fount, the
        # order doesn't matter, but if it's the old fount, then doing it in
        # this order ensures it never actually unpauses, we just hand off one
        # pause for the other.
        if self.fount is not None and self._in.fount.drain is None:
            self._pauseBecauseNoDrain = self.fount.pauseFlow()
        if pbnd is not None:
            pbnd.unpause()


    def receive(self, item):
        """
        
        """
        return self._in.fount.drain.receive(item)


    def flowStopped(self, reason):
        """
        
        """
        return self._in.fount.drain.flowStopped(reason)



@implementer(IFount)
class _InFount(object):
    """
    
    """

    outputType = None

    drain = None

    def __init__(self, fanIn):
        """
        
        """
        self._in = fanIn


    def flowTo(self, drain):
        """
        
        """
        result = beginFlowingTo(self, drain)
        for drain in self._in._drains:
            drain._checkNoDrainPause()
        return result


    def pauseFlow(self):
        """
        
        """
        subPauses = []
        for drain in self._in._drains:
            # XXX wrong because drains could be added and removed
            subPauses.append(drain.fount.pauseFlow())
        return _AggregatePause(subPauses)


    def stopFlow(self):
        """
        
        """
        for drain in self._in._drains:
            drain.fount.stopFlow()



@implementer(IPause)
class _AggregatePause(object):
    """
    
    """

    def __init__(self, subPauses):
        """
        
        """
        self._subPauses = subPauses


    def unpause(self):
        """
        
        """
        for subPause in self._subPauses:
            subPause.unpause()



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
        self.fount = _InFount(self)
        self._drains = []
        self._subdrain = None


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
            L{IFount.flowStopped}
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
    
    """

    fount = None

    def __init__(self, founts, inputType, outputType):
        """
        
        """
        self._pause = None
        self._paused = False

        self._founts = founts

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

        self.inputType = inputType
        self.outputType = outputType


    def flowingFrom(self, fount):
        """
        
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
        
        """
        for fount in self._founts[:]:
            fount._deliverOne(item)


    def flowStopped(self, reason):
        """
        
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

    def __init__(self, inputType=None, outputType=None):
        """
        
        """
        self._founts = []
        self.drain = _OutDrain(self._founts, inputType=inputType,
                               outputType=outputType)


    def newFount(self):
        """
        
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
        L{IFount} from L{flowingFrom <IFount.flowingFrom>}, which means they
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

        @param fount:
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

