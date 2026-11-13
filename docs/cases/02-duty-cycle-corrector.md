# Case study 2: duty-cycle corrector

**Netlist** [`../../netlists/dcc.cir`](../../netlists/dcc.cir) ·
**Specification** [`../../specs/dcc_spec.md`](../../specs/dcc_spec.md) ·
**Run it** `./demo_2_dcc.sh` ·
**Generated output** [`../../showcase/dcc2/`](../../showcase/dcc2/) ·
**Whitepaper** §4

A clock should be high for half of every cycle. The fraction it actually
spends high is its duty cycle, and a duty-cycle corrector puts that fraction
back where it belongs when it has drifted. This one is built around a
comparator.

This is the case that defeats the usual way of modelling and the usual way of
checking, so it is worth reading even if you never build one.

## How fast is this block? Two answers

Nudge the input a little and watch the output move. That is a small-signal
measurement, and the answer is 3.7 × 10⁸ rad/s. Now swing the input hard and
time the output edges directly. The answer is between 1.3 × 10¹⁰ and
5.1 × 10¹⁰ rad/s, which is 35 to 137 times faster.

The slow answer is not wrong, exactly. It measures a sensitive node inside
the comparator, and that node really does respond slowly. But the output is
not taken from that node. It comes from a buffer that slams between the
supply rails without waiting for it. So the slow number is a true fact about
a node the output does not follow, and a model built on it runs tens to
hundreds of times too slow.

The fast answer is not a single number either. It changes by a factor of 3.9
across the input range, so a model with one fixed speed cannot follow it.

### The trap this sets for the usual check

The usual check compares the model's AC (small-signal frequency) response
with the circuit's. Both are measured by nudging, so both report the slow
node, and the two agree beautifully. The check passes a model that is a
hundred times too slow and never breathes a word about it.

Which is why hand-written models of blocks like this one tend to be the ones
people trust least.

## A model that follows how fast the circuit really is

While measuring the circuit, spice2rnm notices that its speed depends on
input level. So it builds a model whose speed varies with level, the way the
measurements say it should. The model also reproduces the circuit's rise/fall
asymmetry: the circuit takes a measured 95 ps longer to switch one way than
the other. Fed a clock that is high exactly half the time, the model's output
duty matches the circuit's to 0.000 percentage points (pp).

| | |
|---|---|
| Transient equivalence | 0.0769 against a 0.15 threshold, **pass** |
| UVM-MS, DC section | 46 checks, 0 failed |
| UVM-MS, duty section | 14 checks, 0 failed |
| worst duty error | 0.428 pp of the specification's 1.0 pp |

The measured rate schedule is in the header of
[`dcc_rnm.sv`](../../showcase/dcc2/dcc_rnm.sv): 33 measured points, and the
94.66 ps rise/fall skew with where it came from. Hand-written models do not
ship with their own evidence. These cannot ship without it.

## Verified by function, not by formula

The UVM-MS environment generated for this block has **no AC section**. That
is a decision taken from measurement, not an oversight.

An AC sweep assumes the circuit sits at one operating point and moves only
gently around it. A comparator in normal use never does that: it slams
between two states. Checked that way, this model fails every single point by
more than 55 dB, even though it is demonstrably accurate. That failure says
nothing about the model and everything about using the wrong check. The run
says so in its own words in
[`pipeline.txt`](../../showcase/dcc2/pipeline.txt).

So the generated environment checks what a duty-cycle corrector is actually
for: the duty of its output.

### The test matrix, and where it came from

The tool drives the transistors in SPICE with clocks at **two rates** and
**three input duties**. Those are the rates and the 35% to 65% duty range the
block's specification states. Each time, the tool records the output duty
SPICE produces, which becomes the golden value, and the model then has to
reproduce those recorded values.

Two frequencies crossed with three starting duties is six conditions. Duty
and frequency are independent properties of a clock, which is why they are
swept as two axes: at 100 MHz the period is 10 ns whatever the duty, and 35%
duty means 3.5 ns high and 6.5 ns low while 50% means 5 ns and 5 ns. The
rising edges land in the same places. Only the falling edges move, and moving
the falling edge without disturbing the rising edges is this block's whole
job.

The recorded duties span 30 percentage points, wide enough that a model
ignoring its input could not pass by luck. That closes an obvious loophole: if
every correct answer were roughly the same number, a model that always
returned a constant would score well by accident.

The golden table is
[`dcc_ms_pkg.sv`](../../showcase/dcc2/dcc_ms_pkg.sv), in the `duty_freq` /
`duty_in` / `duty_gold` / `duty_vth` functions. `duty_vth` is the threshold
each point is sliced at, frozen from ngspice's own trace so the model cannot
influence its own pass. Duty depends on where you measure the crossing, so
pinning the threshold is not a detail.

## The picture, and why an average would mislead

The whitepaper plots one falling edge at the simulator's own time resolution.
The model puts this edge 1.68 ns early and the next one 1.60 ns early, so the
gap between them, which is the duty this block is specified on, survives to
0.03%.

An average voltage error over the whole run would call this a large
disagreement. The duty check the testbench actually applies does not. That is
the case for picking the metric from the block's function rather than using
one error figure everywhere, which
[equivalence.md](../equivalence.md#each-block-is-judged-on-its-own-job) sets
out in general.

## This environment is proven able to fail

The duty-cycle corrector is the block the fault sweep is demonstrated on: the
same testbench run seven times with the model broken in one known way each
time, including a slow-down the DC section is completely blind to. The table
is in
[trusting-a-testbench.md](../trusting-a-testbench.md#every-environment-is-proven-able-to-fail).

## Running the environment yourself

```sh
cd showcase/dcc2
XEZIM=/path/to/xezim UVM_MS_LIB=/path/to/uvm-ms bash run_dcc_ms.sh
```

Expect about 15 minutes: a duty environment samples a trapezoidal clock
hundreds of times per period over many periods. The runner allows an hour
(`WALL_TIMEOUT`, in seconds). If you shorten it and it fires, the run is cut
off *before* the scoreboard reports, which looks deceptively like a clean
pass.

```sh
gtkwave ~/s2r_runs/dcc2_vcd/tb_dcc.vcd
```
