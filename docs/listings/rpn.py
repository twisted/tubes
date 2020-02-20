from tubes.itube import IFrame, ISegment
from tubes.tube import tube, receiver
from tubes.listening import Listener

from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred, inlineCallbacks
from tubes.protocol import flowFountFromEndpoint

class Calculator(object):
    def __init__(self):
        self.stack = []

    def push(self, number):
        self.stack.append(number)

    def do(self, operator):
        left = self.stack.pop()
        right = self.stack.pop()
        result = operator(left, right)
        self.push(result)
        return result

@receiver(inputType=IFrame)
def linesToNumbersOrOperators(line):
    from operator import add, mul
    try:
        yield int(line)
    except ValueError:
        if line == b'+':
            yield add
        elif line == b'*':
            yield mul

@tube
class CalculatingTube(object):
    def __init__(self, calculator):
        self.calculator = calculator

    def received(self, value):
        if isinstance(value, int):
            self.calculator.push(value)
        else:
            yield self.calculator.do(value)

@receiver()
def numbersToLines(value):
    yield str(value).encode("ascii")

@tube
class Prompter(object):
    outputType = ISegment
    def started(self):
        yield b"> "
    def received(self, item):
        yield b"> "

def promptingCalculatorSeries():
    from tubes.fan import Thru
    from tubes.tube import series
    from tubes.framing import bytesToLines, linesToBytes

    full = series(bytesToLines(),
                  Thru([series(linesToNumbersOrOperators,
                               CalculatingTube(Calculator()),
                               numbersToLines,
                               linesToBytes()),
                        series(Prompter())]))
    return full

def calculatorSeries():
    from tubes.tube import series
    from tubes.framing import bytesToLines, linesToBytes

    return series(
        bytesToLines(),
        linesToNumbersOrOperators,
        CalculatingTube(Calculator()),
        numbersToLines,
        linesToBytes()
    )

def mathFlow(flow):
    processor = promptingCalculatorSeries()
    nextDrain = flow.fount.flowTo(processor)
    nextDrain.flowTo(flow.drain)

@inlineCallbacks
def main(reactor, port="stdio:"):
    endpoint = serverFromString(reactor, port)
    flowFount = yield flowFountFromEndpoint(endpoint)
    flowFount.flowTo(Listener(mathFlow))
    yield Deferred()

if __name__ == '__main__':
    from twisted.internet.task import react
    from sys import argv
    react(main, argv[1:])
