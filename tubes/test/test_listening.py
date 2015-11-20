# -*- test-case-name: tubes.test.test_listening -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{tubes.listening}.
"""

from unittest import TestCase

from ..listening import Flow, Listener
from ..memory import iteratorFount

from .util import FakeDrain

class ListeningTests(TestCase):
    """
    Test cases for listening.
    """

    def test_listenerCallsFlowConnector(self):
        """
        A L{Listener} is a drain which calls the function given to it to
        connect a flow
        """
        drained = FakeDrain()
        flow = Flow(iteratorFount([1, 2, 3]),
                    drained)
        flows = []
        fi = iteratorFount([flow])
        listener = Listener(flows.append)
        fi.flowTo(listener)
        self.assertEqual(len(flows), 1)
        results = FakeDrain()
        flows[0].fount.flowTo(results)
        # The listener might need to (and in fact does) interpose a different
        # value for 'fount' and 'drain' to add hooks to them.  We assert about
        # the values passed through them.
        self.assertEqual(results.received, [1, 2, 3])
        iteratorFount([4, 5, 6]).flowTo(flows[0].drain)
        self.assertEqual(drained.received, [4, 5, 6])


    def test_listenerLimitsConcurrentConnections(self):
        """
        L{Listener} will pause its fount when too many connections are
        received.
        """
        connectorCalled = []
        listener = Listener(connectorCalled.append, maxConnections=3)
        tenFlows = iteratorFount([Flow(iteratorFount([1, 2, 3]),
                                       FakeDrain())
                                  for each in range(10)])
        tenFlows.flowTo(listener)
        self.assertEqual(len(connectorCalled), 3)
        connectorCalled[0].fount.flowTo(connectorCalled[0].drain)
