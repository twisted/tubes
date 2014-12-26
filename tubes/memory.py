# -*- test-case-name: tubes.test.test_memory -*-

from twisted.python.failure import Failure

from .tube import _NullFount, tube, series


@tube
class _IteratorTube(object):
    """
    
    """
    def __init__(self, iterable, inputType, outputType):
        """
        
        """
        self.iterable = iterable


    def started(self):
        """
        
        """
        for value in self.iterable:
            yield value

class _NotQuiteNull(_NullFount):
    """
    
    """

    def flowTo(self, drain):
        """
        
        """
        result = super(_NotQuiteNull, self).flowTo(drain)
        drain.flowStopped(Failure(StopIteration()))
        return result


def IteratorFount(iterable, inputType=None, outputType=None):
    """
    
    """
    return _NotQuiteNull().flowTo(
        series(_IteratorTube(iterable, inputType, outputType))
    )



