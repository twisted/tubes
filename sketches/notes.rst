In the interst of making this branch more accessible to additional contributors, here are some thoughts that we have about what's going on right now.

We should be at 100% test coverage.

Framing needs a ton of tests.
It hasn't changed a whole lot so documenting and testing this module might be a good way to get started.

``tubes.protocol`` is pretty well tested and roughly complete but could really use some docstrings, and improve the ones it has.
See for example the docstring for flowFountFromEndpoint.

The objects in ``tubes.protocol``, especially those that show up in log messages, could really use nicer reprs that indicate what they're doing.
For example ``_ProtocolPlumbing`` and ``_FlowFactory`` should both include information about the flow function they're working on behalf of.

Similarly, ``tubes.fan`` is a pretty rough sketch, although it's a bit less self-evident what is going on there since it's not fully implemented.
(*Hopefully* it's straightforward, but let's not count on hope.)

There are a bunch of un-covered `__repr__`s, probably.

`tubes.tube.Diverter` could use some better docstrings, as could its helpers `_DrainingFount` and `_DrainingTube`.

There are some asserts littered around the code.
They all need to be deleted.
Some of them should be replaced with real exceptions, because they're a result of bad inputs, and some of them should be replaced with unit tests that more convincingly prove to us that the internal state can never get into that bad place.

The adapter registry in ``_siphon.py`` is probably silly.
It used to contain a lot more entries, but as the code has evolved it has boiled down into 20 or 30 lines of code and docstrings that might be more easily expressed as a single providedBy check.
Unless more entries show up, we want to delete it and fix ``series`` to just do ``ITube.providedBy`` and inline the implementation of ``tube2drain``.

things that we might want to change
===================================

Currently the contract around flowStopped / stopFlow and then more calls to flowTo / flowingFrom is vague.  We might want to adjust this contract so that a fount that has been stopped or a drain that has received a flowStopped is simply "dead" and may not be re-used in any capacity.  For things like real sockets, this is a fact of life; however, it might just as well be communicated by an instant stopFlow() or flowStopped() upon hook-up.

STATK MAECHINES
---------------

With flowTo in FLOWING (current state, sort of, it's not really implemented all
the way):


Fount
~~~~~

::

    INITIAL -flowTo(None)->    INITIAL,
            -flowTo()->        FLOWING,
            -actuallyPause()-> PAUSED_INITIAL,
            -stopFlow()->      STOPPED;

    PAUSED_INITIAL -actuallyUnpause()-> INITIAL,
                   -actuallyPause()->   PAUSED_INITIAL,
                   -stopFlow()->        STOPPED;

    FLOWING -flowTo(other)->   FLOWING,
            -flowTo(None)->    INITIAL,
            -actuallyPause()-> PAUSED,
            -stopFlow()->      STOPPED;

    PAUSED  -flowTo(other)->    FLOWING,
            -flowTo(None)->     INITIAL,

            ^ note that these are problematic, because you have to re-set the
            pause state, which means you have to discard previous pause tokens,
            which we don't currently do

            -actuallyResume()-> FLOWING,
            -actuallyPause()->  PAUSED,
            -stopFlow()->       STOPPED;

    STOPPED.


Drain
~~~~~

::

    INITIAL -flowingFrom()-> FLOWING,
            -flowingFrom(None)-> INITIAL;

    FLOWING -receive()->     FLOWING,
            -flowingFrom(None)-> INITIAL,
            -flowingFrom(other)-> FLOWING,
            -flowStopped()-> STOPPED;

    STOPPED.


Without flowTo in FLOWING (desired state):


Fount
~~~~~

::

    INITIAL -flowTo()->        FLOWING,
            -actuallyPause()-> PAUSED_INITIAL,
            -stopFlow()->      STOPPED;

    PAUSED_INITIAL -actuallyUnpause()-> INITIAL,
                   -actuallyPause()->   PAUSED_INITIAL,
                   -stopFlow()->        STOPPED;

    FLOWING -actuallyPause()-> PAUSED,
            -stopFlow()->      STOPPED;

    PAUSED  -actuallyResume()-> FLOWING,
            -actuallyPause()->  PAUSED,
            -stopFlow()->       STOPPED;

    STOPPED.


Drain
~~~~~

::

    INITIAL -flowingFrom()-> FLOWING;

    FLOWING -receive()->     FLOWING,
            -flowStopped()-> STOPPED;

    STOPPED.
