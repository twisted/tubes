# -*- test-case-name: tubes.test.test_kit -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Toolkit to alleviate some of the duplication in constructing your own IFount
and IDrain implementations.
"""

from zope.interface import implementer

from .itube import AlreadyUnpaused, IPause


@implementer(IPause)
class _Pause(object):
    """
    Implementation of L{IPause} for L{Pauser}.
    """
    def __init__(self, pauser):
        """
        Construct a L{_Pause} from a L{Pauser}.

        @param pauser: the L{Pauser} that created this L{_Pause}.
        """
        self._friendPauser = pauser
        self._alive = True


    def unpause(self):
        """
        Unpause this L{_Pause}, potentially invoking the C{actuallyResume}
        callback from its L{Pauser}.
        """
        if self._alive:
            self._alive = False
            self._friendPauser._pauses -= 1
            if self._friendPauser._pauses == 0:
                self._friendPauser._actuallyResume()
        else:
            raise AlreadyUnpaused()



class Pauser(object):
    """
    Multiple parties may be interested in suppressing some ongoing concurrent
    activity, each for their own purposes.

    A L{Pauser} maintains the state associated with each of these independent
    pauses, providing an object for each one, making it straightforward for you
    to implement a high-level pause and resume API suitable for use from
    multiple clients, in terms of low-level state change operations.
    """
    def __init__(self, actuallyPause, actuallyResume):
        """
        @param actuallyPause: a callable to be invoked when the underlying
            system ought to transition from paused to unpaused.
        @type actuallyPause: 0-argument callable

        @param actuallyResume: a callable to be invoked when the underlying
            system ought to transition from unpaused to paused.
        @type actuallyPause: 0-argument callable
        """
        self._actuallyPause = actuallyPause
        self._actuallyResume = actuallyResume
        self._pauses = 0


    def pause(self):
        """
        Pause something, getting an L{IPause} provider which can be used to
        unpause it.

        @return: a pause which will invoke the C{actuallyResume} callback if
            it's the last one to be unpaused.
        @rtype: L{IPause}
        """
        self._pauses += 1
        if self._pauses == 1:
            self._actuallyPause()
        return _Pause(self)



def beginFlowingTo(fount, drain):
    """
    To correctly implement fount.flowTo you need to do certain things; do those
    things here.

    @param fount: The fount implementing flowTo.

    @param drain: The drain flowTo was called with.

    @return: the next fount in the chain.
    """
    oldDrain = fount.drain
    fount.drain = drain
    if ( (oldDrain is not None) and (oldDrain is not drain) and
         (oldDrain.fount is fount) ):
        oldDrain.flowingFrom(None)
    if drain is None:
        return
    return drain.flowingFrom(fount)



def beginFlowingFrom(drain, fount):
    """
    To correctly implement drain.flowingFrom you need to do certian things; do
    those things here.

    @param drain: The drain implementing flowingFrom.

    @param fount: The fount flowingFrom was called with.

    @return: L{None}
    """
    if fount is not None:
        outType = fount.outputType
        inType = drain.inputType
        if outType is not None and inType is not None:
            if not inType.isOrExtends(outType):
                raise TypeError(
                    ("the output of {fount}, {outType}, is not compatible "
                     "with the required input type of {drain}, {inType}")
                    .format(inType=inType, outType=outType,
                            fount=fount, drain=drain))
    oldFount = drain.fount
    drain.fount = fount
    if ( (oldFount is not None) and (oldFount is not fount) and
         (oldFount.drain is drain) ):
        oldFount.flowTo(None)



@implementer(IPause)
class NoPause(object):
    """
    A null implementation of L{IPause} that does nothing.
    """

    def unpause(self):
        """
        No-op.
        """



class OncePause(object):
    """
    Pause a pauser once, unpause it if necessary.
    """
    def __init__(self, pauser):
        """
        Create a L{OncePause} with the given L{Pauser}.
        """
        self._pauser = pauser
        self._currentlyPaused = False


    def pauseOnce(self):
        """
        If this L{OncePause} is not currently paused, pause its pauser.
        """
        if not self._currentlyPaused:
            self._currentlyPaused = True
            self._pause = self._pauser.pause()


    def maybeUnpause(self):
        """
        If this L{OncePause} is currently paused, unpause it.
        """
        if self._currentlyPaused:
            self._currentlyPaused = False
            self._pause.unpause()
