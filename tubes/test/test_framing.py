"""
Tests for framing protocols.
"""

from unittest import TestCase

from ..framing import stringsToNetstrings

from ..test.util import FakeFount, FakeDrain
from ..tube import tube, series

from ..framing import (netstringsToStrings, bytesToLines, linesToBytes,
                       packedPrefixToStrings, stringsToPackedPrefix)

class NetstringTests(TestCase):
    """
    Tests for parsing netstrings.
    """

    def test_stringToNetstring(self):
        """
        A byte-string is given a length prefix.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(stringsToNetstrings())).flowTo(fd)
        ff.drain.receive("hello")
        self.assertEquals(fd.received, ["{len:d}:{data:s},".format(
            len=len("hello"), data="hello"
        )])


    def test_stringsToNetstrings(self):
        """
        L{stringsToNetstrings} works on subsequent inputs as well.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(stringsToNetstrings())).flowTo(fd)
        ff.drain.receive("hello")
        ff.drain.receive("world")
        self.assertEquals(
            b"".join(fd.received),
            "{len:d}:{data:s},{len2:d}:{data2:s},".format(
                len=len("hello"), data="hello",
                len2=len("world"), data2="world",
            )
        )


    def test_netstringToString(self):
        """
        Length prefix is stripped off.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(netstringsToStrings())).flowTo(fd)
        ff.drain.receive("1:x,2:yz,3:")
        self.assertEquals(fd.received, ["x", "yz"])



class LineTests(TestCase):
    """
    Tests for parsing delimited data ("lines").
    """

    def test_stringToLines(self):
        """
        A line is something delimited by a LF or CRLF.
        """
        def splitALine(newline):
            ff = FakeFount()
            fd = FakeDrain()
            ff.flowTo(series(bytesToLines())).flowTo(fd)
            ff.drain.receive(newline.join([b"alpha", "beta", "gamma"]))
            self.assertEquals(fd.received, [b"alpha", b"beta"])
        splitALine("\n")
        splitALine("\r\n")


    def test_linesToStrings(self):
        """
        Writing out lines delimits them, with the delimiter.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(linesToBytes())).flowTo(fd)
        ff.drain.receive(b"hello")
        ff.drain.receive(b"world")
        self.assertEquals(b"".join(fd.received), b"hello\r\nworld\r\n")


    def test_rawMode(self):
        """
        You should be able to have some lines, and then some bytes, and then
        some lines.
        """

        lines = bytesToLines()
        ff = FakeFount()
        fd = FakeDrain()

        @tube
        class Switcher(object):
            def received(self, line):
                splitted = line.split(" ", 1)
                if splitted[0] == 'switch':
                    length = int(splitted[1])
                    lines.divert(series(Switchee(length), fd))

        @tube
        class Switchee(object):
            datums = []
            def __init__(self, length):
                self.length = length
            def received(self, data):
                self.datums.append(data)

        cc = series(lines, Switcher())
        ff.flowTo(cc).flowTo(fd)
        ff.drain.receive("hello\r\nworld\r\nswitch 10\r\nabcde\r\nfgh"
                         # + '\r\nagain\r\n'
                         )
        self.assertEquals("".join(Switchee.datums), "abcde\r\nfgh")


    def test_switchingWithMoreDataToDeliver(self):
        """
        Switching drains should immediately stop delivering data.
        """
        lines = bytesToLines()
        ff = FakeFount()
        fd1 = FakeDrain()
        fd2 = FakeDrain()

        @tube
        class Switcher(object):
            def received(self, line):
                if 'switch' in line:
                    lines.divert(series(netstringsToStrings(), fd2))
                else:
                    yield line

        cc = series(lines, Switcher())
        ff.flowTo(cc).flowTo(fd1)
        ff.drain.receive('something\r\nswitch\r\n7:hello\r\n,5:world,')
        self.assertEquals(fd1.received, ["something"])
        self.assertEquals(fd2.received, ['hello\r\n', 'world'])



class PackedPrefixTests(TestCase):
    """
    Test cases for `packedPrefix`.
    """

    def test_prefixIn(self):
        """
        Parse some prefixed data.
        """
        packed = packedPrefixToStrings(8)
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(packed)).flowTo(fd)
        ff.drain.receive(b"\x0812345678\x02")
        self.assertEquals(fd.received, ["12345678"])


    def test_prefixOut(self):
        """
        Emit some prefixes.
        """
        packed = stringsToPackedPrefix(8)
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(packed, fd))
        ff.drain.receive('a')
        ff.drain.receive('bc')
        ff.drain.receive('def')
        self.assertEquals(fd.received, ['\x01a', '\x02bc', '\x03def'])
