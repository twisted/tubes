# -*- test-case-name: tubes.test.test_listening -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Integration test for L{tubes.routing} and L{tubes.fan} implementing a chat
server.
"""

from unittest import TestCase

from zope.interface.common.mapping import IMapping

from tubes.routing import Router, Routed, to
from tubes.tube import series, tube, receiver
from tubes.fan import Out, In

@tube
class Participant(object):
    """
    A single participant in a chat system.
    """
    outputType = Routed(IMapping)

    def __init__(self, hub, requestsFount, responsesDrain):
        """
        Create a L{Participant}.
        """
        self._hub = hub
        self._in = In()
        self._in.fount.flowTo(responsesDrain)

        self._router = Router()
        self._participating = {}

        # `self._in' is both commands from our own client and also messages
        # from other clients.
        requestsFount.flowTo(series(self, self._router.drain))

        self.client = self._router.newRoute("client")
        self.client.flowTo(self._in.newDrain())


    def received(self, item):
        """
        An item was received.

        @param item: A dictionary featuring a 'type' indicating which command
            it is.

        @return: a response routed to the router.
        """
        kwargs = item.copy()
        return getattr(self, "do_" + kwargs.pop("type"))(**kwargs)


    def do_name(self, name):
        """
        From client; set the name of this client.

        @param name: The nickname for this client.
        """
        self.name = name
        yield to(self.client, dict(named=name))


    def do_join(self, channel):
        """
        From client; instruct this client to join a channel with the given
        name.

        @param channel: the name of the channel to join.
        """
        fountFromChannel, drainToChannel = (
            self._hub.channelNamed(channel).participate(self)
        )
        fountFromChannel.flowTo(self._in.newDrain())
        fountToChannel = self._router.newRoute("->{}".format(channel))
        fountToChannel.flowTo(drainToChannel)

        self._participating[channel] = fountToChannel
        yield to(self._participating[channel],
                 dict(type="joined"))


    def do_speak(self, channel, message, id):
        """
        From client; say something on the given channel.

        @param channel: the name of the channel

        @param message: the text of the message to relay

        @param id: a unique identifier for this message
        """
        yield to(self._participating[channel],
                 dict(type="spoke", message=message, id=id))



class Channel(object):
    """
    A chat room.
    """
    def __init__(self, name):
        self._name = name
        self._out = Out()
        self._in = In()
        self._in.fount.flowTo(self._out.drain)


    def participate(self, participant):
        """
        Create a new drain of messages going to this channel and a new fount of
        messages coming from this channel, for the given participant.

        @param participant: the name of the participant joining.

        @return: a 2-tuple of (new fount, new drain)
        """
        @receiver(IMapping, IMapping,
                  name="->addSender({}, {})".format(participant.name,
                                                    self._name))
        def addSender(item):
            yield dict(item, sender=participant.name, channel=self._name)

        return (self._out.newFount(),
                series(addSender, self._in.newDrain()))



@tube
class OnStop(object):
    """
    Utility class to hook 'stopped' with a callable.
    """

    def __init__(self, callback):
        """
        Create an L{OnStop} with a callback.
        """
        self.callback = callback


    def received(self, item):
        """
        We received a message; relay it on unmodified since we only care about
        L{OnStop}.

        @param item: anything
        """
        yield item


    def stopped(self, reason):
        """
        The flow stopped; invoke the given callback.

        @param reason: ignored.

        @return: no results (empty iterable)
        """
        self.callback()
        return ()



class Hub(object):
    """
    A chat hub; the nexus object for a whole channel namespace (i.e.: server).
    """
    def __init__(self):
        self.participants = []
        self.channels = {}


    def newParticipantFlow(self, flow):
        """
        Create a flow for a new participant.

        @param flow: a L{Flow} with a drain and a fount for receiving commands;
            JSON-style dictionaries with a 'type' key indicating which verb to
            invoke on L{Participant}.
        """
        commandFount = flow.fount.flowTo(
            series(OnStop(lambda: self.participants.remove(participant)))
        )
        commandDrain = flow.drain
        participant = Participant(self, commandFount, commandDrain)
        self.participants.append(participant)


    def channelNamed(self, name):
        """
        Retrieve a L{Channel} with the given name.

        @param name: the name of the channel.

        @return: a L{Channel}.
        """
        if name not in self.channels:
            self.channels[name] = Channel(name)
        return self.channels[name]



class ChatTests(TestCase):
    """
    Integration test cases for putting together fan.In and fan.Out in a useful
    configuration for pubsub or multi-user chat.
    """

    def test_joining(self):
        """
        Test that we receive a response from joining.
        """
        from ..listening import Flow
        from .util import FakeFount, FakeDrain
        h = Hub()
        ff = FakeFount()
        fd = FakeDrain()
        h.newParticipantFlow(Flow(ff, fd))
        ff.drain.receive({"type": "name", "name": "bob"})
        self.assertEqual(fd.received.pop(0), {"named": "bob"})
        ff.drain.receive({"type": "join", "channel": "bobs"})
        self.assertEqual(fd.received, [{"type": "joined",
                                        "sender": "bob",
                                        "channel": "bobs"}])
