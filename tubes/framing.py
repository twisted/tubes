# -*- test-case-name: tubes.test.test_framing -*-
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

class _Transporter(object):
    """
    Just enough of a mock of L{ITransport} to work with the protocols in
    L{twisted.protocols.basic}, as a wrapper around a callable taking some
    data.

    @ivar _dataWritten: 1-argument callable taking L{bytes}, a chunk of data
        from a stream.
    """

    def __init__(self, dataWritten):
        self._dataWritten = dataWritten


    def write(self, data):
        """
        Call the C{_dataWritten} callback.
        """
        self._dataWritten(data)


    def writeSequence(self, dati):
        """
        Call the C{_dataWritten} callback for each element.
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
        self._buf = []
        return self._flush()


    def received(self, data):
        self._received(data)
        return self._flush()


    def _unflush(self, input):
        self._buf.append(input)


    def _flush(self):
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
        self._stringReceiver.dataReceived(string)
        u, self._ugh = self._ugh, []
        return u


    def reassemble(self, datas):
        """
        convert these outputs into one of my inputs

        TODO: describe better
        """
        delimiter = self._stringReceiver.delimiter
        # TODO: we don't clear the buffer here (and requiring that we do so is
        # just a bug magnet) so Diverter needs to be changed to have only one
        # input and only one output, and be able to discard the flow in
        # between.
        return delimiter.join(list(datas) + [self._stringReceiver._buffer])



def stringsToNetstrings():
    return _FramesToSegments(NetstringReceiver())



def netstringsToStrings():
    return _SegmentsToFrames(NetstringReceiver())



def linesToBytes():
    return _FramesToSegments(LineOnlyReceiver(), "sendLine")


@tube
class _CarriageReturnRemover(object):
    """
    Automatically fix newlines, because hacker news.
    """

    inputType = IFrame
    outputType = IFrame

    def received(self, value):
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
    delimited by LF, CRLF or some combination thereof.
    """
    return series(Diverter(bytesDelimitedBy("\n")), _CarriageReturnRemover())



_packedPrefixProtocols = {
    8: Int8StringReceiver,
    16: Int16StringReceiver,
    32: Int32StringReceiver,
}

def packedPrefixToStrings(prefixBits):
    return _SegmentsToFrames(_packedPrefixProtocols[prefixBits]())



def stringsToPackedPrefix(prefixBits):
    return _FramesToSegments(_packedPrefixProtocols[prefixBits]())
