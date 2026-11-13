# Case study 4b: the same PLL, in SystemVerilog alone

**Netlist** [`../../netlists/pll_analog.cir`](../../netlists/pll_analog.cir) ·
**Specification** [`../../specs/pll_spec.md`](../../specs/pll_spec.md) ·
**Run it** `./demo_4b_pll_nocosim.sh` ·
**Generated output** [`../../showcase/pll_nocosim/`](../../showcase/pll_nocosim/) ·
**Whitepaper** §6.4

[The previous page](04-pll-cosimulation.md) leans on an SV–SPICE
co-simulation set-up already existing: the digital RTL in the SystemVerilog
simulator, the analog half as transistors in ngspice, and a bridge joining
them. Two steps need it. The golden probe is a run of the design's own
testbench in that co-simulation, against the transistors, and it measures the
range each block really operates over. The system check runs that same
testbench twice. Both need a testbench spanning the two halves, a DPI bridge,
and a shared `libngspice` for the bridge to load.

**Most designs have none of that.** What they have is an analog netlist, some
RTL, a specification in English, and nothing wiring the three together. This
case runs the same PLL that way: SystemVerilog only, RTL plus generated
models, no SPICE anywhere. Call it the SV-only run.

Two things break when you take the co-simulation away.

## Problem one: nothing measures the operating band

A block's operating band is the range of voltages it actually sees in use.
That range is a property of the closed loop, and with the loop open there is
no loop to measure. Worse, two of the ring oscillator's internal nets are
driven by nothing at all, so they have no operating point either.

So the band comes from the two artifacts that do know it, and the run says
which one, for every net. Most of it is sitting in the *deck* and is simply
read off: a source holding a node at one voltage is that node's band, and a
node with a pull-down to ground and a pull-up to the rail cannot leave them.
Two numbers are neither in the netlist nor derivable from it: where a *locked*
loop keeps its control voltage, and how far the supply is allowed to move.
Those two are *declared*, from the operating-conditions table a designer
writes anyway.

Seven messages cover twenty-one nets, five of them facts about the circuit and
two of them design intent:

```
band for 'aout'      DERIVED  as 0..3.3 V, the range its own drivers
                              can reach -- not where it sits; the same
                              for 14 more net(s): xvco.outm1 ...
                              xvco.outm7, xvco.outp1 ... xvco.outp7
band for 'xcp.ss'    DERIVED  as 0 V, fixed: source vss ties it to 0 V
band for 'xvco.ss'   DERIVED  as 0 V, fixed: source vss ties it to 0 V
band for 'xvco.sub'  DERIVED  as 0 V, fixed: source ve ties it to 0 V
band for 'xvco.well' DERIVED  as 3.3 V, fixed: source vpe ties it to 3.3 V
band for 'dd'        DECLARED as 3.13..3.47 V from the specification's
                              'Supply (VDD)' row -- not measured
band for 'vout'      DECLARED as 1.75..1.95 V from the specification's
                              'Control voltage' row -- not measured,
                              because no golden run was available to
                              measure it
```

Nothing on the command line says any of this, and nothing in the
specification names a net. The document says "control voltage". The netlist
says `cont`. The instance card says `cont` is the top level's `vout`. What
ties the three together is the measurement that found which port tunes the
oscillator, so the binding happens after classification and is reported with
the block and port it came from.

These five numbers used to be five `--band` flags on the command line, which
is the one place a number has no owner: it cannot be traced back to the
document that justifies it, it is not reviewed with the design, and a copy of
it in a script drifts away from its source without a sound.

**One more distinction the run keeps.** A band read off a pair of rails is
what a net *can reach*, not where it sits. So it is the weakest of the three,
and it is never narrower than the truth. The charge pump's output can reach
either rail too, and in a locked loop it sits at the control voltage instead.
That topology is recognised and left without a band, rather than given one
that is true and useless.

### A band is an input, not a claim

The operating-conditions table is parsed as plain text, with no language model
involved, while the rest of the document is read by one. The asymmetry is
deliberate. Every other fact taken from a specification gets checked
afterwards against what the circuit was measured to do, and the measurement
wins. A band cannot be checked that way, because it decides the range the
circuit is measured over in the first place. A number with that much
authority must not depend on whether a model happened to be reachable, so it
is read by the part of the toolchain that always runs.

### What the tool took from the specification document

The demonstration hands it the specification along with the netlist and the
RTL. In the run these figures come from:

```
read as: Document states "PLL -- 400 MHz ring-oscillator
  phase-locked loop" with "seven-stage differential ring" whose
  "behaviour is a frequency, not a gain" -> oscillator/vco
  environment; "Output ... 400 MHz" is the highest stated
  frequency; "Reference ... 10 MHz" is the lowest stated rate;
  "20 mV rms of wideband noise is specified on it"; "hold 400 MHz
  to within 2%" and "No small-signal specification ... Do not
  verify any of them against a frequency response" implies
  timing-based verdict; control-voltage swing range quoted as
  "characterizable from 0.5 V to 2.8 V".
```

These are facts about what the part is FOR, which is a different kind of
statement from the operating band above. They choose the stimulus and the
verdict, and they are claims the measurement can contradict. The rule is in
[`../../specs/reading-a-specification.md`](../../specs/reading-a-specification.md):
every fact taken from the document is checked against what the circuit was
measured to do, and the measurement wins. Here nothing disagreed.

### More useful is what it refused to let pass

The document names 20 mV rms of supply noise as a condition the part has to
work under. The reader placed that correctly, in the stimulus rather than the
model. It then reported that the generated environment does not drive it:

```
spec: the document states 20 mV rms of supply noise as a condition
  to work under. That is a property of this block's environment, so
  it belongs in the stimulus rather than in the model
NOTE: the supply-noise condition is not driven by the generated
  environment yet; the composition carries only the noise the
  netlist itself declares
```

So a requirement the tool cannot yet meet gets flagged in the output instead
of quietly dropped. That is the behaviour worth having from a language model
in a verification flow: not a guess at a fix, but a gap it can name.

**It did not supply the five bands.** A person still reads those off the
specification's table and types them on the command line. The run prints the
phrase `a spec DECLARES` for them. That phrase is the band mechanism
labelling a figure a human supplied. It does not mean the reader extracted
it.

**This passage costs the paper some reproducibility.** Every other figure
regenerates identically from its run. The quoted text above does not, because
a language model picks different words each time. What stays stable is
everything around it: the bands, the measurements and the verdicts. All of
those were byte-for-byte identical across this run, across two earlier runs
where the model read the document differently, and across the run before
those, where the reader did not run at all because no model was reachable.
What a model changed was what was *read*, never what was measured.

Neither a derived band nor a declared one is a measured band, and the run
never dresses either up as one. Every message that uses a band names its
source in those words. The blocks the open loop cannot reach say so too,
instead of quietly measuring something else.

## Problem two: per-block models are still not a system

Checking each block on its own does not show that the loop works. Without a
co-simulation, that question still needs an answer, so the SV-only run closes
the loop in *pure SystemVerilog*. It uses the composed models and the
design's own `pfd.sv` and `divn.sv`, instantiated unchanged, in one
simulator. No DPI import, no bridge, no SPICE process anywhere in it.

### The user states no topology

An earlier version of this demonstration shipped a JSON file naming which RTL
port landed on which net. That file is gone. The wiring is followed out from
the one clock the analog half produces, by port *direction*, and not one port
name is read on the way.

That last part is the point, because on this circuit a port name is actively
misleading. In ngspice's own PLL example the detector is instantiated
`Xfpdet d_divout d_ref` against a subcircuit declared
`.subckt f-p-det d_R d_V`. So `d_R` carries the *divided* clock, the opposite
of what it reads like. A loop wired from names is confidently backwards
there.

Here is what the run worked out, and what from:

```
pfd  . ref_clk -> clk_out      divn . clk_in  -> aout_clk
pfd  . div_clk -> ref_clk      divn . clk_out -> clk_out
pfd  . dn      -> dn           analog aout    -> aout_clk
pfd  . up      -> up

the oscillator's control net = vout
    the port block_classify measured as its control source
the net that becomes a clock = aout
    block 'ro_vco' was measured to oscillate on its port 'aout'
the divide ratio = 40
    parameter N of module divn defaults to 40 in its own header
the reference rate = 1.00014e+07 Hz
    the deck holds 'vout' at 1.8495 V, where the measured tuning
    curve puts block 'ro_vco' at 400.056 MHz, and the ratio is 40
```

Every field, with the measurement or file it came from, is recorded in
[`loop/rtl_loop_derivation.json`](../../showcase/pll_nocosim/loop/rtl_loop_derivation.json).
`.alternate.json` beside it is the gate pairing the run did not need.

### One fact about this loop is in neither the netlist nor the measurements

Which of the detector's two outputs speeds the oscillator up is a property of
the RTL's *body*, and both wirings elaborate and run. This used to be settled
by building both loops and keeping whichever one locked. That works, costs a
second loop run every time, and leaves the question answered by an experiment
rather than by the document that ought to state it. The specification states
it instead, in one line that names a port of the customer's RTL and the
control voltage, and no gate of the charge pump:

> **The detector's `up` output raises the control voltage.**

That line is read as text, with no model and no credentials, for the same
reason the operating-conditions table is: it decides how the loop gets
*wired*, so it must not move with whether a model could be called.

And "raises the control voltage" is not "speeds it up". This ring's tuning
curve falls, so the output that raises the control voltage is the *slower*
one. The run does that conversion with the sign it measured, rather than
assuming the two agree. Reading one as the other is exactly the mistake the
statement exists to remove, and on this circuit they point opposite ways.

**The stated sense does not outrank the circuit.** The other pairing is still
written out beside the one that was built, and if the stated one fails to
lock, it is built and run too. A loop that locks is a measurement and a
document is not, so the measurement wins and the run reports the document as
wrong about its own detector. On this deck the stated pairing locked first
time, so one loop was built and the alternative stayed a record.

### Gate polarity comes from measurement

The user does *not* state the polarity of either charge-pump gate, meaning
whether it is active high or active low. The tool works that out from two
things the measuring has already established: the sign of the oscillator's
tuning curve, and the direction of the current each control state drives. The
generated file records the numbers it came from:

```
pdn <- dn, active HIGH (derived)
  ro_vco measured at 15 control points, 0.495 to 2.805 V, over which
    its frequency FALLS 804.47 -> 16.74 MHz: Kvco is NEGATIVE
  lpfilt: current into dra reaches vout through a state space whose
    input vector is non-negative throughout, so positive current
    RAISES it
  with cpump quiescent (pupb=1), pdn at 1 drives -0.00447 A into dra
    and at 0 drives -1.961e-09 A, both at 1.849 V -- active HIGH
pupb <- up, active LOW (derived)
  ... the same two measurements, and with pdn=0, pupb at 1 drives
    -1.961e-09 A into dra -- so its asserted level is the LOW one
```

On this one pump, `pupb` comes out active *low* and `pdn` active *high*. A
port name does not reliably carry that distinction, and charge pumps wired
from their names have shipped upside down before. The four control-state
tables those readings come from are in
[routes.md](../routes.md#control-states).

## Results

| | |
|---|---|
| SV–SPICE co-simulation, at any stage | none |
| Models generated, using four routes | 5 |
| Operating bands | 5 derived, 2 declared, 0 measured |
| Per-block equivalence | 5 of 5 pass |
| Loop closed in | SystemVerilog only |
| Loop sense, stated by the specification | 1 line, no net named |
| Gate polarities derived from measurement | 2 of 2 |
| Gate pairings built and run | 1 of 2, the stated one |
| Divider output vs the reference it follows | 10.001348 vs 10.001401 MHz |
| against a 2% pass/fail limit | −0.0005%, locked |
| Control voltage across the window | 1.8488 to 1.8506 V |
| drift end to end | −0.26 mV |
| Environments generated | 3 per block, 1 over the loop |
| blocks refused, with a reason | 2 |
| run, and reporting results | 4 of 4 |
| Characterisation, loop included | 11 min |
| The four environments, run afterwards | 11 min |

## A UVM-MS environment over the whole loop

All four of this case's environments are published with a run of each beside
them, in
[`showcase/uvm_ms_runs/pll_nocosim/`](../../showcase/uvm_ms_runs/pll_nocosim/).
The loop environment's scoreboard passes its rate, control-window,
tuning-curve and finite checks, 3 each, 0 failed -- and closes by saying that
no transistors were simulated, so a loop settling somewhere plausible and
wrong would pass all of them. That is the case's own weaker claim, in the
environment's words rather than this page's.

The loop above is a plain testbench: it drives a reference clock and checks a
frequency. The SV-only run also generates a full UVM-MS environment around
it, with a sequence, sequencer, driver, monitor, agent and scoreboard. It also
has an MS proxy split in two: an abstract half that the components talk to,
and a concrete half in the top level. Because of that split, neither the
driver nor the monitor holds a hierarchical path into the design.

It is the only *system-level* environment this tool generates with all of
those components. The reason is the stimulus:

| environment | seq | drv | sqr | mon | agt | prx | scoreboard |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| block, transfer function | • | • | • | • | • | • | `uvm_scoreboard` |
| block, oscillator | • | • | • | • | • | • | `uvm_scoreboard` |
| system, SV–SPICE co-simulation | | | | • | • | • | `uvm_scoreboard` |
| system, SV only | • | • | • | • | • | • | `uvm_scoreboard` |

The system environment for the co-simulation run has the observing half and
none of the driving half. The testbench it wraps brings its own stimulus, so
there is nothing for a sequence to ask for. The SV-only run has no such
testbench. Its stimulus is the reference clock, and this environment
generates that clock, so a sequence, a sequencer and a driver all have real
work to do.

The oscillator's block environment uses the same pattern, and the pattern is
what makes both of them extensible. The timing measurement lives in the
proxy's concrete half in `top`, the only scope that can see the design's
signals. The driver, monitor, agent, scoreboard and test hold no references
to either signal, against eight in `top`. A second observer can subscribe to
the monitor's analysis port without restructuring anything. And *one*
implementation of "time a clock" serves both this environment and the loop
one.

### The reference rate is not a round number any more

It is the measured tuning curve read at the control voltage the deck states,
divided by the ratio the divider's own header declares: 1.8495 V puts the ring
at 400.056 MHz, and 40 of those make 10.001402 MHz. The loop environment's
sequence and driver use that timing to step the reference frequency up by
0.5% and back down again. That is why the results below have three
measurement windows instead of one settled snapshot. A model frozen at its
initial condition would produce a single settled snapshot too, so one snapshot
proves little.

### Its expected values come from two places, and every line says which

Two come from the specification: reach the reference frequency within
tolerance, and keep the control voltage inside the stated window. Two come
from this run's own measurements, and the second of those is the valuable
one. The oscillator's tuning curve was measured point by point in ngspice
before any of this existed. Invert that curve at the frequency the loop is
asked for and you get the control voltage the oscillator needs to produce it.

| Window | divider output | control voltage |
|---|---|---|
| nominal, 10.001402 MHz | 10.001342 | 1.8488 to 1.8505 V |
| stepped, 10.051409 MHz | 10.050600 | 1.8435 to 1.8457 V |
| returned, 10.001402 MHz | 10.000518 | 1.8490 to 1.8506 V |

| Check | Result | Source |
|---|---|---|
| rate, against a 2% bar | 3 checks, 0 failed, worst 0.0088% | [SPEC] |
| control window, 1.75 to 1.95 V | 3 checks, 0 failed | [SPEC] |
| against the measured curve | 3 checks, 0 failed, worst 0.89 mV | [MEASURED] |
| boundary finite | 3 checks, 0 failed | [MEASURED] |

**The stepped window is the one to read.** The reference went *up* and the
control voltage went *down*, which is what a negative K<sub>vco</sub>
requires. It also went down by the amount the measured curve predicts. From
its 15 points, that curve puts 400 MHz at 1.8496 V, with ±2% spanning 1.8291
to 1.8705 V. The loop settles 0.89 mV from the prediction, inside a window
41.5 mV wide.

**That check is worth reporting because it can fail.** A loop can reach the
right frequency at the wrong control voltage: through a charge pump with the
wrong sign, a wrongly fitted slope, or a divider ratio the reference happens
to absorb. Counting clock edges cannot see any of that. Shift the measured
table by 100 mV and exactly those three checks fail, by about that same
100 mV, while the two specification checks still pass. **An environment built
only from the specification would have passed the same run.**

## All four environments are run, not merely generated

Three per-block environments are generated beside the loop one: one for each
of the two clock buffers, and one for the oscillator. Two blocks are refused,
with the reason written out. The charge pump's result is a current for each
control state, and the filter's is a voltage produced by an injected current.
Every generated environment scores a voltage against a stimulus, so neither
of those fits.

A file count shows that a generator produced something. It says nothing about
whether the output elaborates, compiles against the Accellera UVM library, or
scores anything. So each environment is executed and its scoreboard result
reported:

| Environment | what its scoreboard concluded | time |
|---|---|---|
| `inv1` | 54 DC checks, 0 failed, worst 0.001 mV of a 6.6 mV bar | 6 s |
| `inv2` | 54 DC checks, 0 failed | 111 s |
| `ro_vco` | 15 breakpoint + 5 held-out, 0 failed, worst 0.024% | 219 s |
| the loop | 12 checks over 3 windows, 0 failed | 336 s |

All four are published, and all four were run from the published copy rather
than from the run directory, so what is published is exactly what ran.

## What this result does not carry

There are two limits here, and neither one is small.

**First, there are no transistors in this loop**, so nothing in the SV-only
run is evidence about the circuit itself. A loop that settles at a plausible
but wrong point still settles, and only
[the co-simulation run](04-pll-cosimulation.md) can catch that. The verdict
covers this modelled loop, at this reference frequency, starting from the
initial condition the netlist states.

**Second, this run's 5 of 5 is not the same 5 of 5** as the co-simulation
run's. A clock buffer's verdict only means anything with the duty-cycle
metric, and that metric needs the clock's frequency. The golden probe is what
measures that frequency, and the SV-only run has no golden probe. So `inv1`
and `inv2` fall back to comparing average voltage: 0.021 and 0.026 against a
0.15 bar. Both pass, but that check is blind to where the clock edges fall,
for exactly the reason given in
[the previous page](04-pll-cosimulation.md#where-the-block-works-is-measured-not-assumed).
The two runs agree on the count and differ on what the count is worth.
