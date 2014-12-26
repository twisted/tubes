# -*- test-case-name: tubes.test.test_kit -*-

"""
Toolkit to alleviate some of the duplication in constructing your own IFount
and IDrain implementations.
"""

from zope.interface import implementer

from .itube import AlreadyUnpaused, IPause


@implementer(IPause)
class _Pause(object):
    def __init__(self, pauser):
        self._friendPauser = pauser
        self._alive = True


    def unpause(self):
        if self._alive:
            self._friendPauser._pauses -= 1
            if self._friendPauser._pauses == 0:
                self._friendPauser._actuallyResume()
            self._alive = False
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

        @rtype: L{IPause}
        """
        if not self._pauses:
            self._actuallyPause()
        self._pauses += 1
        return _Pause(self)



def beginFlowingTo(fount, drain):
    """
    to correctly implement fount.flowTo you need to do certain things; do those
    things here
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
    to correctly implement drain.flowingFrom you need to do certian things; do
    those things here
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

