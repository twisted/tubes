# -*- test-case-name: tubes.test.test_undefer -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{Deferred} support for Tubes.
"""

from .tube import receiver, series, skip

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



