
from twisted.tubes.protocol import factoryFromFlow
from twisted.tubes.itube import IFrame, ISegment
from twisted.tubes.tube import tube, receiver

from twisted.internet.endpoints import serverFromString
from twisted.internet.defer import Deferred

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
        if line == '+':
            yield add
        elif line == '*':
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
    inputType = ISegment
    outputType = ISegment
    def started(self):
        yield "> "
    def received(self, item):
        yield "> "

def promptingCalculatorSeries():
    from twisted.tubes.fan import Thru
    from twisted.tubes.tube import series
    from twisted.tubes.framing import bytesToLines, linesToBytes

    full = series(bytesToLines(),
                  Thru([series(linesToNumbersOrOperators,
                               CalculatingTube(Calculator()),
                               numbersToLines,
                               linesToBytes()),
                        series(Prompter())]))
    return full

def calculatorSeries():
    from twisted.tubes.tube import series
    from twisted.tubes.framing import bytesToLines, linesToBytes

    return series(
        bytesToLines(),
        linesToNumbersOrOperators,
        CalculatingTube(Calculator()),
        numbersToLines,
        linesToBytes()
    )

def mathFlow(fount, drain):
    processor = calculatorSeries()
    nextDrain = fount.flowTo(processor)
    nextDrain.flowTo(drain)

def main(reactor, port="stdio:"):
    endpoint = serverFromString(reactor, port)
    endpoint.listen(factoryFromFlow(mathFlow))
    return Deferred()

from twisted.internet.task import react
from sys import argv
react(main, argv[1:])
