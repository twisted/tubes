# -*- test-case-name: tubes.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interfaces related to data flows.
"""

from zope.interface import Interface, Attribute

if 0:
    from zope.interface.interfaces import ISpecification
    ISpecification
    from twisted.python.failure import Failure
    Failure



class AlreadyUnpaused(Exception):
    """
    The L{IPause} has already been unpaused.
    """



class StopFlowCalled(Exception):
    """
    L{IFount.stopFlow} was called, and that's why the flow was stopped.
    """



class IPause(Interface):
    """
    A L{pause <IPause>} is a reason that an L{IFount} is not delivering output
    to its C{drain} attribute.  This reason may be removed by L{unpausing
    <IPause.unpause>} the pause.
    """

    def unpause():
        """
        Remove this L{IPause} from the set of L{IPause}s obstructing delivery
        from an L{IFount}.  When no L{IPause}s remain, the flow will resume.

        The spice must flow.

        @raise AlreadyUnpaused: An L{IPause} may only be C{unpause}d once; it
            can not be re-paused.  Therefore a second invocation of this
            method is invalid and will raise an L{AlreadyUnpaused} exception.
        """



class IFount(Interface):
    """
    A fount produces objects for a drain to consume.
    """

    outputType = Attribute(
        """
        The type of output produced by this Fount.

        This may be an L{ISpecification} provider.
        """)

    drain = Attribute(
        """
        The L{IDrain} currently accepting input from this L{IFount}.
        (Read-only; should raise L{AttributeError} if set.)
        """)


    def flowTo(drain):
        """
        Add a drain to this fount to consume its output.

        This will I{synchronously} call L{flowingFrom(fount)
        <IDrain.flowingFrom>} on C{drain} to indicate to C{drain} which
        L{IFount} its future input will come from - I{unless} this L{IFount} is
        exhausted and will never produce more output.  In this case, C{flowTo}
        must I{not} call C{flowingFrom}, and must return L{None}.

        Typically, this will return the result of L{drain.flowingFrom(fount)
        <IDrain.flowingFrom>} to allow construction of pipelines with the
        C{x.flowTo(...).flowTo(...).flowTo(...)} idiom; however,
        implementations of L{IFount} are at liberty to return L{None} or any
        valid L{IFount}.

        @raise AlreadyDraining: if there is already a drain (i.e.  C{flowTo}
            has already been called on this L{IFount}.)

        @return: another L{IFount} provider, or C{None}.  By convention, this
            will return the value of C{flowingFrom} and allow the drain to
            transform the C{outputType} (however, other transformations are
            allowed).
        """

    def pauseFlow():
        """
        Temporarily refrain from delivery of items to this L{IFount}'s C{drain}
        attribute.

        @return: a L{pause token <IPause>} which may be used to remove the
            impediment to this L{IFount}'s flow established by this call to
            C{pauseFlow}.  Multiple calls will result in multiple tokens, all
            of which must be unpaused for the flow to resume.
        @rtype: L{IPause}
        """

    def stopFlow():
        """
        End the flow from this L{IFount}; after this invocation, this L{IFount}
        should never call any methods on its C{drain} other than
        L{self.drain.flowStopped() <IDrain.flowStopped>}.  It will invoke
        C{flowStopped} once, when the resources associated with this L{IFount}
        flowing have been released.
        """



class IDrain(Interface):
    """
    A drain consumes objects from a fount.
    """

    inputType = Attribute(
        """
        Similar to L{IFount.outputType}.

        This is an L{ISpecification} provider.
        """)

    fount = Attribute(
        """
        The fount that is delivering data to this L{IDrain}.
        """)


    def flowingFrom(fount):
        """
        This drain is now accepting a flow from the given L{IFount}.

        @param fount: A fount, or L{None} if no further input will be received.
        @type fount: L{IFount} or L{types.NoneType}

        @return: another L{IFount}, if this L{IDrain} will produce more data,
            or C{None}.
        """

    def receive(item):
        """
        An item was received from the fount.

        @param item: an instance of L{IDrain.inputType}

        @return: a floating point number between 0.0 and 1.0, indicating the
            how full any buffers on the way to processing the data are
            (0-100%).  Note that this may be greater than 100%, in which case
            you should probably stop sending for a while and give it a chance
            to recover.
        """

    def flowStopped(reason):
        """
        The flow has stopped.  The given L{Failure} object indicates why.
        After a L{IFount} invokes this method, it must stop invoking all other
        methods on this L{IDrain}; similarly, this L{IDrain} must stop invoking
        all methods on its L{IFount}.

        @param reason: The reason why the flow has terminated.  This may
            contain any exception type, depending on the L{IFount} delivering
            data to this L{IDrain}.
        @type reason: L{Failure}
        """



class ITube(Interface):
    """
    A tube transforms input into output.

    Look at this awesome ASCII art::

                         a fount
                      +----+--------+               +-----  a
                     / +---+------+ | | data flow  / +----  fount
         a tube --->/ /           | | v           / /
                   / /            | |            / /
                  / /             | |  a drain  / /
        a     ---+ /              | +----+-----+ /<--- a tube
        drain ----+               +------+------+

              =========> direction of flow =========>

    (Image credit Nam Nguyen)

    @note: L{ITube} providers participate in I{data processing} not in I{flow
        control}.  That is to say, an L{ITube} provider can translate its input
        to output, but cannot impact the rate at which that output is
        delivered.  If you want to implement flow-control modifications,
        implement L{IDrain} directly.  L{IDrain} providers may be easily
        connected up to L{ITube} providers with L{series
        <tubes.tube.series>}, so you may implement flow-control in an
        L{IDrain} that passes on its input unmodified and data-processing in an
        L{ITube} and hook them together.
    """

    inputType = Attribute(
        """
        The type expected to be received as input to received.
        """
    )

    outputType = Attribute(
        """
        The type expected to be sent as output to C{tube.deliver}.
        """
    )

    def started():
        """
        The flow of items has started.  C{received} may be called at any point
        after this.
        """

    def received(item):
        """
        An item was received from 'upstream', i.e. the framework, or the
        lower-level data source that this L{ITube} is interacting with.

        @return: An iterable of values to propagate to the downstream drain
            attached to this L{ITube}.
        @rtype: iterable of L{ITube.outputType}
        """

    def stopped(reason):
        """
        The flow of data from this L{ITube}'s input has ceased; this
        corresponds to L{IDrain.flowStopped}.

        @note: L{ITube} I{has} no notification corresponding to
            L{IFount.stopFlow}, since it has no control over whether additional
            data will be synthesized / processed by I{its} fount, there's no
            useful work it can do.

        @return: The same as L{ITube.received}; values returned (or yielded) by
            this method will be propagated before the L{IDrain.flowStopped}
            notification to the downstream drain.
        @rtype: same as L{ITube.received}
        """



class IDivertable(ITube):
    """
    An L{IDivertable} is an L{ITube} which may have its input diverted away
    from it.
    """

    def reassemble(data):
        """
        Reverse the transformation done by calling L{received}, so as to
        provide any buffered output as input to the drain where this
        L{IDivertable} is being diverted.

        @param data: The objects which had been returned from L{ITube.received}
            which had been buffered.
        @type data: L{list}

        @return: A list of objects such that, if L{received} was called
            successively with each object in the returned list, C{tube.deliver}
            would be called successively with each object in C{data}.  This
            does not need to be exactly equal to what was originally passed in
            as long as it achieves the same effect.  Any objects which were
            buffered by the L{IDivertable} which did not yet correspond to a
            C{tube.deliver} call should be included as well.
        @rtype: L{list}
        """



class ISegment(Interface):
    """
    This is a marker interface for a L{bytes} which represents the
    arbitrarily-sized segments of data that a stream-oriented protocol may
    deliver; contrast with L{IFrame}.
    """



class IFrame(Interface):
    """
    This is a marker interface for a L{bytes} which represents a discrete,
    separated sequence of bytes within a protocol; contrast with L{ISegment}.
    """
