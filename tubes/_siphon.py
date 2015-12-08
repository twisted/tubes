# -*- test-case-name: tubes.test.test_tube -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Adapters for converting L{ITube} to L{IDrain} and L{IFount}.
"""

from collections import deque

from zope.interface import implementer

from .itube import IDrain, IFount, ITube
from .kit import Pauser, beginFlowingFrom, beginFlowingTo, NoPause, OncePause
from ._components import _registryAdapting

from twisted.python.failure import Failure

from twisted.python import log

whatever = object()



def suspended():
    """
    A token value meaning that L{SiphonPendingValues} was suspended.
    """



def finished():
    """
    A token value meaning that L{SiphonPendingValues} has no more values in its
    queue.
    """



def skip():
    """
    A token value yielded by a tube meaning that its L{_Siphon} should not
    deliver this value on, so that tubes may engage in flow control.
    """



class SiphonPendingValues(object):
    """
    A queue of pending values which can be suspended and resumed, for
    representing values pending delivery for a L{_Siphon}.

    @ivar _deque: a deque containing iterators containing queued values.

    @ivar _suspended: Is this L{SiphonPendingValues} currently suspended?
    """

    def __init__(self):
        self._deque = deque()
        self._suspended = False


    def suspend(self):
        """
        L{SiphonPendingValues.popPendingValue} should return L{suspended}.
        """
        self._suspended = True


    def resume(self):
        """
        L{SiphonPendingValues.popPendingValue}
        """
        self._suspended = False


    def prepend(self, iterator):
        """
        Add the given iterator to the beginning of the queue.

        @param iterator: an iterator of values to deliver via popPendingValue.
        """
        self._deque.appendleft(iterator)


    def append(self, iterator):
        """
        Add the given iterator to the end of the queue.

        @param iterator: an iterator of values to deliver via popPendingValue.
        """
        self._deque.append(iterator)


    def clear(self):
        """
        Clear the entire queue.
        """
        self._deque.clear()


    def popPendingValue(self, evenIfSuspended=False):
        """
        Get the next value in the leftmost iterator in the deque.

        @param evenIfSuspended: return the next pending value regardless of
            whether this L{SiphonPendingValues} is suspended or not.
        @type evenIfSuspended: L{bool}

        @return: The next value yielded by the first iterator in the queue,
            L{suspended} if this L{SiphonPendingValues} is suspended and
            C{evenIfSuspended} was not passed, or L{finished} if the queue is
            empty.
        """
        if self._suspended and not evenIfSuspended:
            return suspended
        while self._deque:
            result = next(self._deque[0], whatever)
            if self._suspended and not evenIfSuspended:
                self.prepend(iter([result]))
                return suspended
            if result is whatever:
                self._deque.popleft()
            else:
                return result
        return finished



class _SiphonPiece(object):
    """
    Shared functionality between L{_SiphonFount} and L{_SiphonDrain}
    """
    def __init__(self, siphon):
        self._siphon = siphon


    @property
    def _tube(self):
        """
        Expose the siphon's C{_tube} directly since many things will want to
        manipulate it.

        @return: L{ITube}
        """
        return self._siphon._tube



@implementer(IFount)
class _SiphonFount(_SiphonPiece):
    """
    Implementation of L{IFount} for L{_Siphon}.

    @ivar fount: the implementation of the L{IDrain.fount} attribute.  The
        L{IFount} which is flowing to this L{_Siphon}'s L{IDrain}
        implementation.

    @ivar drain: the implementation of the L{IFount.drain} attribute.  The
        L{IDrain} to which this L{_Siphon}'s L{IFount} implementation is
        flowing.
    """
    drain = None

    def __init__(self, siphon):
        super(_SiphonFount, self).__init__(siphon)

        def _actuallyPause():
            fount = self._siphon._tdrain.fount
            self._siphon._pending.suspend()
            if fount is not None:
                pbpc = fount.pauseFlow()
            else:
                pbpc = NoPause()
            self._siphon._pauseBecausePauseCalled = pbpc

        def _actuallyResume():
            fp = self._siphon._pauseBecausePauseCalled
            self._siphon._pauseBecausePauseCalled = None

            self._siphon._pending.resume()
            self._siphon._unbufferIterator()

            fp.unpause()

        self._pauser = Pauser(_actuallyPause, _actuallyResume)


    def __repr__(self):
        """
        Nice string representation.
        """
        return "<Fount for {0}>".format(repr(self._siphon._tube))


    @property
    def outputType(self):
        """
        Relay the C{outputType} declared by the tube.

        @return: see L{IFount.outputType}
        """
        return self._tube.outputType


    def flowTo(self, drain):
        """
        Flow data from this L{_Siphon} to the given drain.

        @param drain: see L{IFount.flowTo}

        @return: an L{IFount} that emits items of the output-type of this
            siphon's tube.
        """
        result = beginFlowingTo(self, drain)
        self._siphon._pauseBecauseNoDrain.maybeUnpause()
        self._siphon._unbufferIterator()
        return result


    def pauseFlow(self):
        """
        Pause the flow from the fount, or remember to do that when the fount is
        attached, if it isn't yet.

        @return: L{IPause}
        """
        return self._pauser.pause()


    def stopFlow(self):
        """
        Stop the flow from the fount to this L{_Siphon}, and stop delivering
        buffered items.
        """
        self._siphon._noMore(input=True, output=True)
        fount = self._siphon._tdrain.fount
        if fount is None:
            return
        fount.stopFlow()



@implementer(IDrain)
class _SiphonDrain(_SiphonPiece):
    """
    Implementation of L{IDrain} for L{_Siphon}.
    """
    fount = None

    def __repr__(self):
        """
        Nice string representation.
        """
        return '<Drain for {0}>'.format(self._siphon._tube)


    @property
    def inputType(self):
        """
        Relay the tube's declared inputType.

        @return: see L{IDrain.inputType}
        """
        return self._tube.inputType


    def flowingFrom(self, fount):
        """
        This siphon will now have 'receive' called on it by the given fount.

        @param fount: see L{IDrain.flowingFrom}

        @return: see L{IDrain.flowingFrom}
        """
        beginFlowingFrom(self, fount)
        if self._siphon._pauseBecausePauseCalled:
            pbpc = self._siphon._pauseBecausePauseCalled
            self._siphon._pauseBecausePauseCalled = None
            if fount is None:
                pauseFlow = NoPause
            else:
                pauseFlow = fount.pauseFlow
            self._siphon._pauseBecausePauseCalled = pauseFlow()
            pbpc.unpause()
        if fount is not None:
            if not self._siphon._canStillProcessInput:
                fount.stopFlow()
            # Is this the right place, or does this need to come after
            # _pauseBecausePauseCalled's check?
            if not self._siphon._everStarted:
                self._siphon._everStarted = True
                self._siphon._deliverFrom(self._tube.started)
        nextFount = self._siphon._tfount
        nextDrain = nextFount.drain
        if nextDrain is None:
            return nextFount
        return nextFount.flowTo(nextDrain)


    def receive(self, item):
        """
        An item was received.  Pass it on to the tube for processing.

        @param item: an item to deliver to the tube.
        """
        def tubeReceivedItem():
            return self._tube.received(item)
        self._siphon._deliverFrom(tubeReceivedItem)


    def flowStopped(self, reason):
        """
        This siphon's fount has communicated the end of the flow to this
        siphon.  This siphon should finish yielding its current buffer, then
        yield the result of it's C{_tube}'s C{stopped} method, then communicate
        the end of flow to its downstream drain.

        @param reason: the reason why our fount stopped the flow.
        """
        self._siphon._noMore(input=True, output=False)
        self._siphon._flowStoppingReason = reason
        def tubeStopped():
            return self._tube.stopped(reason)
        self._siphon._deliverFrom(tubeStopped)



class _Siphon(object):
    """
    A L{_Siphon} is an L{IDrain} and possibly also an L{IFount}, and provides
    lots of conveniences to make it easy to implement something that does fancy
    flow control with just a few methods.

    @ivar _tube: the L{ITube} which will receive values from this siphon and
        call C{deliver} to deliver output to it.  (When set, this will
        automatically set the C{siphon} attribute of said L{ITube} as well, as
        well as un-setting the C{siphon} attribute of the old tube.)

    @ivar _currentlyPaused: is this L{_Siphon} currently paused?  Boolean:
        C{True} if paused, C{False} if not.

    @ivar _pauseBecausePauseCalled: an L{IPause} from the upstream fount,
        present because pauseFlow has been called.

    @ivar _flowStoppingReason: If this is not C{None}, then call C{flowStopped}
        on the downstream L{IDrain} at the next opportunity, where "the next
        opportunity" is when all buffered input (values yielded from
        C{started}, C{received}, and C{stopped}) has been written to the
        downstream drain and we are unpaused.

    @ivar _everStarted: Has this L{_Siphon} ever called C{started} on its
        L{ITube}?
    @type _everStarted: L{bool}
    """

    def __init__(self, tube):
        """
        Initialize this L{_Siphon} with the given L{ITube} to control its
        behavior.
        """
        self._canStillProcessInput = True
        self._pauseBecausePauseCalled = None
        self._tube = None
        self._everStarted = False
        self._unbuffering = False
        self._flowStoppingReason = None

        self._tfount = _SiphonFount(self)
        self._pauseBecauseNoDrain = OncePause(self._tfount._pauser)
        self._tdrain = _SiphonDrain(self)
        self._tube = tube
        self._pending = SiphonPendingValues()


    def _noMore(self, input, output):
        """
        I am now unable to produce further input, or output, or both.

        @param input: L{True} if I can no longer produce input.

        @param output: L{True} if I can no longer produce output.
        """
        if input:
            self._canStillProcessInput = False
        if output:
            self._pending.clear()


    def __repr__(self):
        """
        Nice string representation.
        """
        return '<_Siphon for {0}>'.format(repr(self._tube))


    def _deliverFrom(self, deliverySource):
        """
        Deliver some items from a callable that will produce an iterator.

        @param deliverySource: a 0-argument callable that will return an
            iterable.
        """
        try:
            iterableOrNot = deliverySource()
        except:
            f = Failure()
            log.err(f, "Exception raised when delivering from {0!r}"
                    .format(deliverySource))
            self._tdrain.fount.stopFlow()
            downstream = self._tfount.drain
            if downstream is not None:
                downstream.flowStopped(f)
            return
        if iterableOrNot is None:
            return
        self._pending.append(iter(iterableOrNot))
        if self._tfount.drain is None:
            self._pauseBecauseNoDrain.pauseOnce()
        self._unbufferIterator()


    def _unbufferIterator(self):
        """
        Un-buffer some items buffered in C{self._pending} and actually deliver
        them, as long as we're not paused.
        """
        if self._unbuffering:
            return

        self._unbuffering = True

        while True:
            value = self._pending.popPendingValue()
            if value is suspended:
                break
            elif value is skip:
                continue
            elif value is finished:
                if self._flowStoppingReason:
                    self._endOfLine(self._flowStoppingReason)
                break
            else:
                self._tfount.drain.receive(value)

        self._unbuffering = False


    def _endOfLine(self, flowStoppingReason):
        """
        We've reached the end of the line.  Immediately stop delivering all
        buffers and notify our downstream drain why the flow has stopped.

        @param flowStoppingReason: the reason that the flow was stopped.
        """
        self._noMore(input=True, output=True)
        self._flowStoppingReason = None
        self._pending.clear()
        downstream = self._tfount.drain
        if downstream is not None:
            self._tfount.drain.flowStopped(flowStoppingReason)


    def ejectPending(self):
        """
        Eject the entire pending buffer into a list for reassembly by a
        diverter.

        @return: a L{list} of all buffered output values.
        """
        result = []
        while True:
            value = self._pending.popPendingValue(evenIfSuspended=True)
            if value is finished:
                return result
            result.append(value)



def _tube2drain(tube):
    """
    An adapter that can convert an L{ITube} to an L{IDrain} by wrapping it in a
    L{_Siphon}.

    @param tube: L{ITube}

    @return: L{IDrain}
    """
    return _Siphon(tube)._tdrain



_tubeRegistry = _registryAdapting(
    (ITube, IDrain, _tube2drain),
)



