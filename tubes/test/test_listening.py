
from unittest import TestCase

from zope.interface import implementer

from tubes.listening import Flow
from tubes.listening import Listener
from tubes.memory import iteratorFount
from tubes.itube import IDrain

@implementer(IDrain)
class Collector(object):
    """
    
    """
    inputType = None

    fount = None

    def __init__(self):
        """
        
        """
        self.collected = []

    def flowingFrom(self, fount):
        """
        
        """


    def receive(self, item):
        """
        
        """
        self.collected.append(item)


    def flowStopped(self, reason):
        """
        flow stopped!
        """
        



class ListeningTest(TestCase):
    """
    Test cases for listening.
    """

    def test_listenerCallsFlowConnector(self):
        """
        A L{Listener} is a drain which calls the function given to it to
        connect a flow
        """
        drained = Collector()
        flow = Flow(iteratorFount([1, 2, 3]),
                    drained)
        flows = []
        fi = iteratorFount([flow])
        listener = Listener(flows.append)
        fi.flowTo(listener)
        self.assertEqual(len(flows), 1)
        results = Collector()
        flows[0].fount.flowTo(results)
        # The listener might need to (and in fact does) interpose a different
        # value for 'fount' and 'drain' to add hooks to them.  We assert about
        # the values passed through them.
        self.assertEqual(results.collected, [1, 2, 3])
        iteratorFount([4, 5, 6]).flowTo(flows[0].drain)
        self.assertEqual(drained.collected, [4, 5, 6])


    def test_listenerLimitsConcurrentConnections(self):
        """
        L{Listener} will pause its fount when too many connections are
        received.
        """
        connectorCalled = []
        listener = Listener(connectorCalled.append, maxConnections=3)
        tenFlows = iteratorFount([Flow(iteratorFount([1, 2, 3]),
                                       Collector())
                                  for each in range(10)])
        tenFlows.flowTo(listener)
        self.assertEqual(len(connectorCalled), 3)
        connectorCalled[0].fount.flowTo(connectorCalled[0].drain)
