# -*- test-case-name: tubes.test.test_undefer -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{Deferred} support for Tubes.
"""

from .tube import receiver, series, skip
from .itube import IDrain

from zope.interface import implementer
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

def deferredToResult():
    """
    Convert L{Deferred}s into their results.

    @return: a L{drain <tubes.tube.IDrain>} that receives L{Deferred}s and
        emits the values that are the results of those L{Deferred}s.
    """
    @receiver()
    def received(item):
        if isinstance(item, Deferred):
            pause = selfAsFount.pauseFlow()
            results = []
            def done(result):
                results[:] = [result]
                pause.unpause()
            item.addBoth(done)
            yield skip
            [result] = results
            if isinstance(result, Failure):
                result.raiseException()
            else:
                yield result

    drain = series(received)
    selfAsFount = drain.flowingFrom(None)
    return drain



@implementer(IDrain)
class _DeferredAggregatingDrain(object):
    """
    A L{_DeferredAggregatingDrain} aggregates a fount's results into a
    Deferred.
    """
    inputType = None
    fount = None

    def __init__(self, deferred):
        """
        Create a L{_DeferredAggregatingDrain} from a L{Deferred}.
        """
        self._values = []
        self._deferred = deferred


    def flowingFrom(self, fount):
        """
        The flow has begun; do nothing.

        @param fount: The fount.
        """


    def receive(self, item):
        """
        An item was received.  Remember it.

        @param item: The item.
        """
        self._values.append(item)


    def flowStopped(self, reason):
        """
        The flow was stopped.  Fire the L{Deferred}.

        @param reason: The reason; ignored.
        """
        values, self._values = self._values, None
        self._deferred.callback(values)



def fountToDeferred(fount):
    """
    Convert the given C{fount} to a L{Deferred} that consumes and aggregates
    all the results of said C{fount}.

    @param fount: A fount which, at this point, should have no drain.
    @type fount: L{tubes.itube.IFount}

    @return: a L{Deferred} that fires with an iterable
    @rtype: L{Deferred} firing iterable of C{fount.outputType}
    """
    d = Deferred(fount.stopFlow)
    fount.flowTo(_DeferredAggregatingDrain(d))
    return d
