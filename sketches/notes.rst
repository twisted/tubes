In the interst of making this branch more accessible to additional contributors, here are some thoughts that we have about what's going on right now.

Framing needs a ton of tests.
It hasn't changed a whole lot so documenting and testing this module might be a good way to get started.

``twisted.tubes.protocol`` is pretty well tested and roughly complete but could really use some docstrings, and improve the ones it has.
See for example the docstring for factoryFromFlow.

The objects in ``twisted.tubes.protocol``, especially those that show up in log messages, could really use nicer reprs that indicate what they're doing.
For example ``_ProtocolPlumbing`` and ``_FlowFactory`` should both include information about the flow function they're working on behalf of.

Similarly, ``twisted.tubes.fan`` is a pretty rough sketch, although it's a bit less self-evident what is going on there since it's not fully implemented.
(*Hopefully* it's straightforward, but let's not count on hope.)

There are a bunch of un-covered `__repr__`s, probably.

`twisted.tubes.tube.Diverter` could use some better docstrings, as could its helpers `_DrainingFount` and `_DrainingTube`.

We need a decorator for a function so that this:

.. code-block:: python

    class Foo(Tube):
        def receive(self, item):
            yield item

can become this:

.. code-block:: python

    @receiver
    def Foo(item):
        yield item

exactly how to map the name Foo or foo or whatever is left as an exercise for the reader, but defining things with just receive seems to be a thing to do all over the place.

We need a QueueFount, something where you construct it with a maximum size, and then can push in a value and have it delivered onwards to its drain, or buffered if it is currently paused.
"push" is not the same as "receive" because QueueFount's contract should be to raise an exception if too many values are provided before the drain can consume them all, something that ``receive`` should never do because ``receive`` will pause the fount if there's too much traffic.
Raising an exception like this is a way of applying backpressure to a python program that is producing too much data rather than to a "real" data source.

QueueFount would be useful for testing applications that are built on top of tubes, so that a test could simply construct one and deliver it to the system under test without setting up I/O.
We presently need it in order to write simpler examples that explain how data flows work and operate on sample data without necessarily dealing with real sockets and transports in the first example.
Only the *last*, fully-integrated example really ought to have that sort of concern.
Having to explain all this stuff up front makes all the introductory prose very unweildy.

It would be nice to have a constructor or utility function that constructs a QueueFount from a list so you don't have to call "push" yourself a bunch of times.

There are some asserts littered around the code.
They all need to be deleted.
Some of them should be replaced with real exceptions, because they're a result of bad inputs, and some of them should be replaced with unit tests that more convincingly prove to us that the internal state can never get into that bad place.

The adapter registry in ``_siphon.py`` is probably silly.
It used to contain a lot more entries, but as the code has evolved it has boiled down into 20 or 30 lines of code and docstrings that might be more easily expressed as a single providedBy check.
Unless more entries show up, we want to delete it and fix ``series`` to just do ``ITube.providedBy`` and inline the implementation of ``tube2drain``.


things that we might want to change
===================================

We might want to make ``flowTo`` into a function because almost any correct implementation of ``flowTo`` has the same half a dozen or so logical checks to be correct.

    - If a fount has an old drain, it should call ``flowingFrom(None)`` on that drain in order to notify it that the old drain should no longer interact with the fount.  This is to prevent plan interference of various types where the old drain will cause its old fount to pause, stop, and so on.
    - Open question: whether we make it an independent function or not, we may need to re-set the 'pause' state and discard all old pause tokens.  Consider: we have a fount, it's flowing to a drain, various consumers of that drain's information are holding pause tokens.  Now, we're no longer flowing to that drain, so as we just said, that drain (and its subsidiary components) should no longer pause that fount: it follows that they should no longer resume that fount, either.  (This also implies that a fount with no drain may not be paused.  Hmm.)
    - Updating the ``drain`` attribute.
    - ``flowingFrom`` may re-entrantly call ``flowTo`` (with itself or with a different drain), or it may call any other method on the same ``fount``: ``pauseFlow``, or ``stopFlow``.
    - it needs to handle the special case of ``None`` and remember not to call any methods on ``None``.

One possible alternate approach is that we have a ``flowTo`` function which:

    - updates the fount attribute on the drain
    - updates the drain attribute on the fount
    - calls flowStarted on the drain
    - calls startFlow on the fount
    - returns the result of flowingFrom

If implemented this way, the per-fount and per-drain code no longer need to handle the ``flowingFrom(None)`` notification because that can be generally handled by ``flowTo``.

Currently the contract around flowStopped / stopFlow and then more calls to flowTo / flowingFrom is vague.  We might want to adjust this contract so that a fount that has been stopped or a drain that has received a flowStopped is simply "dead" and may not be re-used in any capacity.

Rather than making flowTo a function, we might also want to make a concrete ``FountHelper`` class that we use for implementing all of our founts, and make the interface that real data sources implement be a lower-level thing that you have to wrap a ``FountHelper`` around.  This would mean that, for example, ``Pauser`` could go away, because the lower-level interface would simply have an ``actuallyPause`` and ``actuallyResume``.  (TBD: should ``FountHelper`` be public?)

Assuming that ``IFount`` doesn't change, that inner interface would consist of ``actuallyPause``, ``actuallyResume``, ``flowedToSomething`` which would be executed only after ``flowTo`` processed a valid new drain (i.e. after possibly calling ``flowingFrom(None)`` and updating the drain attribute and earlying out if the new drain is ``None`` and calling ``flowingFrom`` and afterwards it would propagate the return value of ``flowingFrom).


things you have to know (in ``flowingFrom``)

you have to know if you're flowing from no fount
you have to know if you're flowing to a different fount

in both of those cases you have to flowTo(None) your old fount, so that the old fount knows that it can't deliver data to you any more.

you have to do this _BEFORE_ you unpause it.

you have to know if you're flowing to the same fount


what if, instead of re-flowing in order to divert a flow, you got a new fount from an object whose entire job was producing a new fount

flowTo() is now linear, can only be called once.



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
