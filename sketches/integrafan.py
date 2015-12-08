from __future__ import print_function

from uuid import uuid4
from json import dumps

from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.task import LoopingCall

from twisted.protocols.basic import LineReceiver

class OneChatter(LineReceiver, object):
    def connectionMade(self):
        q = [
                {"type": "name", "name": unicode(uuid4())},
                {"type": "join", "channel": "testing"},
        ] + [
            {"type": "speak", "channel": "testing",
             "message": unicode(x), "id": unicode(uuid4())}
            for x in range(3)
        ]
        def nextq():
            if q:
                expr = q.pop(0)
                print("sending", expr)
                self.sendLine(dumps(expr))
            else:
                lc.stop()

        lc = LoopingCall(nextq)
        lc.start(0.1)

    def dataReceived(self, data):
        print("data received", repr(data))
        super(OneChatter, self).dataReceived(data)

    def lineReceived(self, line):
        print(repr(line))


endpoint = TCP4ClientEndpoint(reactor, "localhost", 4321)
endpoint.connect(Factory.forProtocol(OneChatter))
reactor.run()
