# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Tests for framing protocols.
"""

from unittest import TestCase

from ..framing import bytesToNetstrings

from ..test.util import FakeFount, FakeDrain
from ..tube import tube, series

from ..framing import (netstringsToBytes, bytesToLines, linesToBytes,
                       bytesToIntPrefixed, intPrefixedToBytes)

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
        ff.flowTo(series(bytesToNetstrings())).flowTo(fd)
        ff.drain.receive(b"hello")
        self.assertEquals(
            fd.received, [b"%(len)d:%(data)s," %
                          {b"len": len(b"hello"), b"data": b"hello"}]
        )


    def test_bytesToNetstrings(self):
        """
        L{bytesToNetstrings} works on subsequent inputs as well.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(bytesToNetstrings())).flowTo(fd)
        ff.drain.receive(b"hello")
        ff.drain.receive(b"world")
        self.assertEquals(
            b"".join(fd.received),
            b"%(len)d:%(data)s,%(len2)d:%(data2)s," % {
                b"len": len(b"hello"), b"data": b"hello",
                b"len2": len(b"world"), b"data2": b"world",
            }
        )


    def test_netstringToString(self):
        """
        Length prefix is stripped off.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(netstringsToBytes())).flowTo(fd)
        ff.drain.receive(b"1:x,2:yz,3:")
        self.assertEquals(fd.received, [b"x", b"yz"])



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
            ff.drain.receive(newline.join([b"alpha", b"beta", b"gamma"]))
            self.assertEquals(fd.received, [b"alpha", b"beta"])
        splitALine(b"\n")
        splitALine(b"\r\n")


    def test_linesToBytes(self):
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
                splitted = line.split(b" ", 1)
                if splitted[0] == b'switch':
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
        ff.drain.receive(b"hello\r\nworld\r\nswitch 10\r\nabcde\r\nfgh"
                         # + '\r\nagain\r\n'
                         )
        self.assertEquals(b"".join(Switchee.datums), b"abcde\r\nfgh")


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
                if b'switch' in line:
                    lines.divert(series(netstringsToBytes(), fd2))
                else:
                    yield line

        cc = series(lines, Switcher())
        ff.flowTo(cc).flowTo(fd1)
        ff.drain.receive(b'something\r\nswitch\r\n7:hello\r\n,5:world,')
        self.assertEquals(fd1.received, [b"something"])
        self.assertEquals(fd2.received, [b'hello\r\n', b'world'])



class PackedPrefixTests(TestCase):
    """
    Test cases for `packedPrefix`.
    """

    def test_prefixIn(self):
        """
        Parse some prefixed data.
        """
        packed = bytesToIntPrefixed(8)
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(packed)).flowTo(fd)
        ff.drain.receive(b"\x0812345678\x02")
        self.assertEquals(fd.received, [b"12345678"])


    def test_prefixOut(self):
        """
        Emit some prefixes.
        """
        packed = intPrefixedToBytes(8)
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(series(packed, fd))
        ff.drain.receive(b'a')
        ff.drain.receive(b'bc')
        ff.drain.receive(b'def')
        self.assertEquals(fd.received, [b'\x01a', b'\x02bc', b'\x03def'])
