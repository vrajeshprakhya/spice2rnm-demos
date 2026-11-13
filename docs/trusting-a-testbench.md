# Why a green testbench is worth believing

**Whitepaper** §9

Generated verification has an obvious credibility problem. The same tool
writes the model *and* writes the test. What stops it from writing a test its
own model is bound to pass?

Three rules.

## The right answers come from SPICE, never from the model

Every expected value in every generated environment is a golden value: a
SPICE measurement of your circuit. Check a model against the equations it
implements and it passes however wrong it is. So spice2rnm never does that.

The rule is stated in the header of every generated scoreboard. Open
[`../showcase/dcc2/dcc_ms_scoreboard.svh`](../showcase/dcc2/dcc_ms_scoreboard.svh)
or
[`../showcase/lpf2/rc_lpf2_ms_scoreboard.svh`](../showcase/lpf2/rc_lpf2_ms_scoreboard.svh)
and read the first lines.

## Every environment is proven able to fail

The tool breaks the generated model on purpose and confirms the test goes red.
It also *measures* the smallest break the test still catches, rather than just
claiming there is one.

The example is
[the duty-cycle corrector's](cases/02-duty-cycle-corrector.md) published
environment, the one judged against its specification's 1.0 pp requirement
(pp means percentage points of duty cycle). The same testbench was run seven
times, each time with the model broken in one known way:

| Injected fault | DC section | duty section | worst duty error |
|---|---|---|---|
| none | 46 pass | 14 pass | 0.43 pp |
| comparator offset, +5 mV | 1 fails | pass | 0.43 pp |
| comparator offset, +20 mV | 1 fails | pass | 0.73 pp |
| comparator offset, +50 mV | 2 fail | pass | 0.77 pp |
| dynamics slowed 2× | pass | pass | 0.65 pp |
| dynamics slowed 10× | pass | pass | 0.87 pp |
| dynamics slowed 50× | pass | 9 fail | 14.3 pp |

**The table says two things.**

First, the DC section is blind to *any* error in how fast the block responds.
Slow the model down fiftyfold and all 46 of its DC checks still pass. Yet DC
checks are all that many hand-written environments contain. The duty section
exists to cover that blind spot, and it is the only check here that catches
the slowed model.

Second, the table shows where the test stops catching things, and why. A
tenfold slow-down shifts the output duty by 0.87 pp. That is under the 1 pp
the specification allows, so the test passes. The tool's own default limit for
this environment is 0.5 pp, which would have failed it.

**An environment built from a specification is exactly as strict as the
specification, and no stricter.** That is on purpose. A requirement is what
the circuit is held to, and an environment that quietly applied a tighter
limit would report failures the design does not have.

What the fault sweep adds is the number. You now know that this specification
cannot catch a tenfold error in the block's speed, and you can decide whether
that is the requirement you meant to write.

## The test is checked in both directions

A test that fails everything is as useless as one that passes everything. So
the same sweep also confirms that small, acceptable errors do *not* trip the
environment. The unbroken model passes, and a 5 mV offset moves the duty
cycle by nothing the duty section should object to.

## The sweep is re-run, so the table cannot drift

It runs against the shipped model whenever the environment changes, so the
table always describes the environment you get. That is why this table
differs from an earlier one measured against the default limit. The claims
stay measured results instead of drifting into folklore nobody rechecks.

## Two smaller guards worth knowing about

**The environment instantiates the model itself**, not a copy behind a
wrapper, so the checks cover exactly what ships. Where a model does ship
inside a port wrapper, the generated testbench drives that wrapper and the
wrapper's file joins the compile list. See
[joining-a-model-library.md](joining-a-model-library.md).

**A check that does not apply is reported as not applicable**, with the
reason, and never counted as a pass. The duty-cycle corrector's missing AC
section and the phase interpolator's missing DC and AC sections are both of
these: a decision taken from measurement, written down in the run log.
