
from collections import defaultdict
from json import loads, dumps

from zope.interface.common import IMapping

from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred

from twisted.tubes.routing import Router, Routed, to
from twisted.tubes.protocol import factoryFromFlow
from twisted.tubes.itube import IFrame
from twisted.tubes.tube import series, tube, receiver
from twisted.tubes.framing import bytesToLines, linesToBytes
from twisted.tubes.fan import Out, In




@tube
class Participant(object):
    outputType = Routed(IMapping)

    def __init__(self, hub, requestsFount, responsesDrain):
        self._hub = hub
        self._participation = {}
        self._in = In()
        self._router = Router()
        self._participating = {}

        # self._in is both commands from our own client and also messages from
        # other clients.
        requestsFount.flowTo(self._in.newDrain())
        self._in.fount.flowTo(series(self, self._router.drain))

        self.client = self._router.newRoute()
        self.client.flowTo(responsesDrain)

    def received(self, item):
        return getattr(self, "do_" + item.pop("type"))(**item)

    def do_name(self, name):
        self.name = name
        yield to(self.client, dict(named=name))

    def do_join(self, channel):
        fountFromChannel, drainToChannel = (
            self._hub.channelNamed(channel).participate(self)
        )
        fountFromChannel.flowTo(self._in.newDrain())
        fountToChannel = self._router.newRoute()
        fountToChannel.flowTo(drainToChannel)

        self._participating[channel] = fountToChannel
        yield to(self.client,
                 dict(type="joined", channel="channel"))
        yield to(self._participating[channel],
                 dict(type="joined"))

    def do_speak(self, channel, message, id):
        yield to(self._participating[channel],
                 dict(type="spoke", message=message, id=id))
        yield to(self.client, dict(type="spoke", id=id))

    def do_shout(self, message, id):
        for channel in self._participating.values():
            yield to(channel, dict(type="spoke", message=message, id=id))
        yield to(self.client, dict(type="shouted", id=id))

    def do_tell(self, receiver, message):
        # TODO: implement _establishRapportWith; should be more or less like
        # joining a channel.
        rapport = self._establishRapportWith(receiver)
        yield to(rapport, dict(type="told", message=message))
        # TODO: when does a rapport end?  timeout as soon as the write buffer
        # is empty?

    def do_told(self, sender, message):
        yield to(self.client, message)

    def do_spoke(self, channel, sender, message):
        yield to(self.client, dict(type="spoke", channel=channel,
                                   sender=sender.name, message=message))



@receiver(IFrame, IMapping)
def linesToCommands(line):
    yield loads(line)



@receiver(IMapping, IFrame)
def commandsToLines(message):
    yield dumps(message)



class Channel(object):
    def __init__(self, name):
        self._name = name
        self._out = Out()
        self._in = In()
        self._in.fount.flowTo(self._out.drain)

    def participate(self, participant):
        @receiver(IMapping, IMapping)
        def addSender(item):
            yield dict(item, sender=participant, channel=self._name)

        return (self._out.newFount(),
                series(addSender, self._in.newDrain()))



@tube
class OnStop(object):
    def __init__(self, callback):
        self.callback = callback
    def received(self, item):
        yield item
    def stopped(self, reason):
        self.callback()
        return ()



class Hub(object):
    def __init__(self):
        self.participants = []
        self.channels = defaultdict(Channel)

    def newParticipantFlow(self, fount, drain):
        commandFount = fount.flowTo(
            series(OnStop(lambda: self.participants.remove(participant)),
                   bytesToLines(), linesToCommands)
        )
        commandDrain = series(commandsToLines, linesToBytes(), drain)
        participant = Participant(self, commandFount, commandDrain)
        self.participants.append(participant)

    def channelNamed(self, name):
        return self.channels[name]



def main(reactor, port="stdio:"):
    endpoint = serverFromString(reactor, port)
    endpoint.listen(factoryFromFlow(Hub().newParticipantFlow))
    return Deferred()



from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
