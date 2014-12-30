# -*- test-case-name: tubes.test.test_memory -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Founts and drains that can produce values from static data in memory.
"""

from twisted.python.failure import Failure

from .tube import _NullFount, tube, series


@tube
class _IteratorTube(object):
    """
    An L{_IteratorTube} is an L{ITube} delivering the values from an iterable.
    """

    def __init__(self, iterable):
        """
        Create an L{_IteratorTube} from the given iterable.
        """
        self.iterable = iterable


    def started(self):
        """
        Deliver all the values in the iterable as a greeting.
        """
        for value in self.iterable:
            yield value



class _NotQuiteNull(_NullFount):
    """
    A L{_NotQuiteNull} is a fount that delivers a L{StopIteration} flowStopped
    after yielding its values.
    """

    def flowTo(self, drain):
        """
        Start the flow as usual and then immediately stop it with
        L{StopIteration}.

        @param drain: The drain to deliver to.

        @return: the next fount in the series.
        """
        result = super(_NotQuiteNull, self).flowTo(drain)
        drain.flowStopped(Failure(StopIteration()))
        return result



def iteratorFount(iterable):
    """
    Create and return an L{IFount} that delivers the values from the given
    iterator.

    @param iterable: an iterable of any values.

    @return: a fount which will deliver the given iterable to its drain.
    """
    return _NotQuiteNull().flowTo(series(_IteratorTube(iterable)))



