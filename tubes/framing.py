# -*- test-case-name: tubes.test.test_framing -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tubes that can convert streams of data into discrete chunks and back again.
"""

from zope.interface import implementer

from .itube import IDivertable, IFrame, ISegment
from .tube import tube, series, Diverter
from twisted.protocols.basic import (
    LineOnlyReceiver, NetstringReceiver, Int8StringReceiver,
    Int16StringReceiver, Int32StringReceiver
)

if 0:
    # Workaround for inability of pydoctor to resolve references.
    from twisted.internet.interfaces import ITransport
    ITransport
    from twisted.protocols import basic
    basic



class _Transporter(object):
    """
    Just enough of a mock of L{ITransport} to work
    with the protocols in L{basic}, as a wrapper around a
    callable taking some data.

    @ivar _dataWritten: 1-argument callable taking L{bytes}, a chunk of data
        from a stream.
    """

    def __init__(self, dataWritten):
        self._dataWritten = dataWritten


    def write(self, data):
        """
        Call the C{_dataWritten} callback.

        @param data: The data to write.
        @type data: L{bytes}
        """
        self._dataWritten(data)


    def writeSequence(self, dati):
        """
        Call the C{_dataWritten} callback for each element.

        @param dati: The sequence of data to write.
        @type dati: L{list} of L{bytes}
        """
        for data in dati:
            self._dataWritten(data)



@tube
class _FramesToSegments(object):
    """
    A tube which could convert "L{frames <IFrame>}" - discrete chunks of data -
    into "L{segments <ISegment>}" - parts of a raw data stream, with framing
    headers or delimiters attached.

    @param _received: the C{sendString} method, a 1-argument callable taking
        L{bytes}.
    @type _received: L{callable}
    """

    inputType = IFrame
    outputType = ISegment

    def __init__(self, stringReceiver, sendMethodName="sendString"):
        stringReceiver.makeConnection(_Transporter(self._unflush))
        self._received = getattr(stringReceiver, sendMethodName)


    def started(self):
        """
        Flush any greeting data that has come from the wrapped framing parser.

        @return: any bytes written by makeConnection
        """
        self._buf = []
        return self._flush()


    def received(self, data):
        """
        A frame was received, manipulate it and yield a segment or segments.

        @param data: a frame.

        @return: a sequence of segments with appropriate framing information
            embedded to frame C{data}.
        """
        self._received(data)
        return self._flush()


    def _unflush(self, input):
        """
        Put the given segments into the output buffer.

        @param input: some values written to the underlying receiver's
            transport.
        @type input: L{bytes}
        """
        self._buf.append(input)


    def _flush(self):
        """
        Clear the output buffer and return its previous contents.

        @return: the current output buffer.
        @rtype: L{list} of L{bytes}, each representing a segment.
        """
        self._buf, x = [], self._buf
        return x



class _NotDisconnecting(object):
    """
    Enough of a transport to pretend to not be disconnecting.
    """
    disconnecting = False



@implementer(IDivertable)
@tube
class _SegmentsToFrames(object):
    """
    Convert segments into frames by parsing them.
    """

    inputType = ISegment
    outputType = IFrame

    def __init__(self, stringReceiver,
                 receivedMethodName="stringReceived"):
        self._stringReceiver = stringReceiver
        self._ugh = []
        setattr(self._stringReceiver, receivedMethodName,
                lambda aaaugh: self._ugh.append(aaaugh))
        self._stringReceiver.makeConnection(_NotDisconnecting())


    def received(self, string):
        """
        Some data was received on the wire.

        @param string: a segment, to be parsed into frames.

        @return: an iterable of frames.
        """
        self._stringReceiver.dataReceived(string)
        u, self._ugh = self._ugh, []
        return u


    def reassemble(self, datas):
        """
        Take the given sequence of frames, previously emitted by this
        L{_SegmentsToFrames}, combine it with any un-parsed data still in the
        input buffer, and return a list of segments.

        @param datas: L{list} of L{bytes} representing frames.

        @return: L{list} of L{bytes} representing segments.
        """
        delimiter = self._stringReceiver.delimiter
        # TODO: we don't clear the buffer here (and requiring that we do so is
        # just a bug magnet) so Diverter needs to be changed to have only one
        # input and only one output, and be able to discard the flow in
        # between.

        # TODO: won't work for anything that doesn't have a delimiter
        # attribute, so... pretty much nothing but LineReceiver.
        return [delimiter.join(list(datas) + [self._stringReceiver._buffer])]



def bytesToNetstrings():
    """
    Create a new tube for converting a stream of byte segments containing
    DJB-style netstrings into bytes.

    @return: a L{tube <ITube>} that splits a stream of L{segments <ISegment>}
        containing nestrings into L{frame <IFrame>}.
    """
    return _FramesToSegments(NetstringReceiver())



def netstringsToBytes():
    """
    Create a new tube for encoding a sequence of discrete frames of bytes into
    DJB-style netstrings on the wire.

    @return: a L{tube <ITube>} that puts netstring length encoding around
        L{frames <IFrame>} to produce L{segments <ISegment>}.
    """
    return _SegmentsToFrames(NetstringReceiver())



def linesToBytes():
    """
    Convert lines into bytes.

    @return: Create a new tube for adding CRLF delimiters to a sequence of
        lines (frames) to produce bytes (segments).
    """
    return _FramesToSegments(LineOnlyReceiver(), "sendLine")



@tube
class _CarriageReturnRemover(object):
    """
    Automatically fix newlines, because hacker news.
    """

    inputType = IFrame
    outputType = IFrame

    def received(self, value):
        """
        Remove a trailing linefeed, if present, from value and yield it.

        @param value: a line that has already been split up on \\n.
        """
        if value.endswith(b'\r'):
            yield value[:-1]
        else:
            yield value



def bytesDelimitedBy(delimiter):
    """
    Consumes a stream of bytes and produces frames delimited by the given
    delimiter.

    @param delimiter: an octet sequence that separates frames in the incoming
        stream of bytes.
    @type delimiter: L{bytes}

    @return: a tube that converts a stream of bytes into a sequence of frames.
    @rtype: L{ITube}
    """
    receiver = LineOnlyReceiver()
    receiver.delimiter = delimiter
    return _SegmentsToFrames(receiver, "lineReceived")



def bytesToLines():
    """
    Create a drain that consumes a stream of bytes and produces frames
    delimited by LF or CRLF.

    @return: a new L{IDrain} that does the given conversion.
    """
    return series(Diverter(bytesDelimitedBy(b"\n")), _CarriageReturnRemover())



_packedPrefixProtocols = {
    8: Int8StringReceiver,
    16: Int16StringReceiver,
    32: Int32StringReceiver,
}

def bytesToIntPrefixed(prefixBits):
    """
    Convert a sequence of byte segments with packed network-endian int prefixes
    of the given bit width into frames of the indicated sizes.

    @param prefixBits: The number of bits to use for the length prefix: either
        8, 16, or 32.

    @return: a new L{ITube} that does the conversion.
    """
    return _SegmentsToFrames(_packedPrefixProtocols[prefixBits]())



def intPrefixedToBytes(prefixBits):
    """
    Prepend packed network endian lengths to a sequence of bytes representing
    frames.

    @param prefixBits: The number of bits to use for the length prefix: either
        8, 16, or 32.

    @return: a new L{ITube} that does the conversion.
    """
    return _FramesToSegments(_packedPrefixProtocols[prefixBits]())
