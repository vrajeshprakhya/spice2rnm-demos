# Case study 4: phase-locked loop, checked against the transistors

**Netlist** [`../../netlists/pll_analog.cir`](../../netlists/pll_analog.cir) ·
**RTL** [`../../rtl/pll/`](../../rtl/pll/) ·
**Run it** `./demo_4_pll.sh` ·
**Generated output** [`../../showcase/pll_cosim/`](../../showcase/pll_cosim/) ·
**Whitepaper** §6 to §6.3

The first three case studies are single blocks. This one is a *loop*, and
that changes what a model has to get right. In a loop a small error does not
stay small. It gets fed back round and moves the whole system to a different
operating point. So a model that looks reasonable on its own can still park
the loop somewhere the real circuit never goes.

The same circuit is also run with no SPICE at all, on
[the next page](05-pll-systemverilog-only.md).

## Three measuring problems in one netlist

The blocks are the netlist's own `.subckt` boundaries:

```spice
.subckt ro_vco aout cont dd
  ...                        (supplies, and the wires closing the ring)
  xinv1  dd ss sub well cont inm1  inp1  outm1 outp1 gaincell
  ...                                    (7 ring stages)
  xinv11 dd 0  sub well outm1 outm2 inv1
  xinv12 dd 0  sub well outm2 aout  inv2
.ends ro_vco

xcp  pupb pdn dra dd  cpump
xlf  dra vout         lpfilt
xvco aout vout dd     ro_vco
```

The top level has three `x` lines (subcircuit instances), so three models get
joined into the runnable whole. `inv1` and `inv2` are instantiated one level
down, inside `ro_vco`. They get models of their own and verdicts of their
own, which is why the score below is five of five and not three of three.
They are not wired into the composed top, because the `ro_vco` model was
measured with them already inside it. `gaincell` gets no model at all: it has
two inputs and two outputs, so no method that fits one input to one output
can measure it, and the composed model does not need one.

Each remaining block is classified from its topology and given a *route*,
meaning the measuring method chosen for that block:

| Block | Why the default does not fit | Route taken |
|---|---|---|
| `ro_vco` | oscillates with its inputs at DC; its output is a frequency, not a gain | tuning curve, scored on rate |
| `cpump` | a complementary pair driven from independently controlled gates | one *I(V)* table per control state |
| `lpfilt` | only R and C, so its state space is exact and needs no fitting | exact state space, read from topology |

Not one of the three is a simple input-to-output response. A conventional
flow that fitted one to each block would be fitting the wrong quantity three
times over. [routes.md](../routes.md) explains what a tuning curve, a control
state and a state space are, using this circuit's own numbers.

## Checked as a whole system, against the transistors

A score for each block tells you about that block and nothing else. A loop
asks a different question: wired together, do these models behave like the
circuit?

An SV–SPICE co-simulation answers it directly. The design's own testbench is
run twice. In the first run the analog half is the generated models, all in
SystemVerilog. In the second it is the transistors in ngspice, co-simulated
with the digital RTL. **The only thing that changes between the runs is the
small piece of code joining the two halves.** The thresholds, the expressions
and the pass/fail logic are byte-for-byte identical, so the two logs can be
compared line by line.

| | |
|---|---|
| Blocks modelled, three routes | 3 composed, 2 more generated |
| Per-block equivalence | 5 of 5 pass |
| Supply noise | 20 mV rms, declared in the netlist |
| System check vs transistor-level circuit | 4 boundary signals, 0 failed |
| `vout` (control voltage) | 4.158 mV, 47% of its pass/fail limit |
| `aout` (VCO output) | 0.4% of crossings, limit 2% |
| `dra` (internal probe) | 20.0 mV, 0.9% of its range |
| Both loops lock at | 400.00 MHz |
| control voltage range, transistors | 1.8453 to 1.8563 V |
| control voltage range, models | 1.8482 to 1.8522 V |
| Model half vs transistor half | 4.98 s vs 173.6 s |
| same testbench, same span | 35× |

### Read the speed-up row with suspicion

It depends on how busy the machine is. Between the two most recent runs of
this netlist the model half went from 4.37 to 4.98 s while the transistor half
went from 81.8 to 173.6 s. The ratio moved from 19× to 35× with nothing about
the models changing. A shared machine slows the transistor run far more than
the model one, so both halves move together and the ratio follows whichever
is more exposed. The speed-up is real, but it is a property of the machine as
much as of the models, and four runs in a row have now put it at 16×, 24×,
19× and 35×.

### The control voltage is the number to read

The loop keeps its state there, so a model that settles in the wrong place
shows it here first. The two runs agree to 4.158 mV and reach the same
frequency. They do it with 20 mV rms of random noise on the supply, as the
netlist declares. The agreement is looser than it was with a quiet supply,
and the supply noise is why: a loop funnels a supply disturbance onto exactly
this node.

The whitepaper plots it: the composed models against the transistors, on the
design's own testbench, on a node the loop holds near 1.85 V. Both settle to
the same place and stay there. There are eight points because the digital side
reads this node eight times.

## The agreement figure changes from run to run, and so does part of the limit

What the agreement itself has to beat does not.

The supply noise is random. Each run makes its own noise from the source the
netlist declares, so the model run and the transistor run never see the same
noise. The largest difference between them, over any time window, therefore
changes from run to run. Eleven runs in a row of this same netlist gave 3.61,
1.83, 4.15, 2.05, 1.86, 1.72, 4.62, 3.851, 1.783, 4.077 and the 4.158 mV
quoted above: eleven draws spanning a factor of 2.7. Two of the eleven were
run back to back with nothing changed between them.

So the figure in the table is one draw from a spread of possible results, not
a property of the model. The two most recent runs happen to agree to 2%, while
two others differ by more than a factor of two.

**The limit it is judged against has two parts, and only one of them is
fixed.** The agreement itself must come within 0.05 of `vout`'s own scale, in
this run and in every other. On top of that sits an allowance for run-to-run
variation, and that allowance is *measured*, not declared: it is three
standard errors of the difference between two window means, taken from how
much the SPICE reference itself moved in this run. So it moves when the noise
reaching the node moves. On the nine runs before the last two it came out at
0.128, for a limit of 0.178. On those two the reference was noisier on `vout`:
0.194 and now 0.189, for limits of 0.244 and 0.239. The 4.158 mV works out at
0.112 against that limit, comfortably inside.

That ratio is what the verdict rests on, and the record keeps the allowance
separately from the 0.05 so a reader can see which part of the limit moved.

The scale has a minimum of its own: 2% of the node's magnitude. Without that
minimum the comparison would be unfair here. In the transistor run `vout`
moved only 11.1 mV across the window, and measuring a difference against so
small a range would report ordinary noise as error.

In general, an agreement figure quoted without its limit tells you less than
it looks like it does.

### Each node also records which metric its limit applies to

The digital side reads some nodes through a threshold. For those, what
matters is when the signal crosses the threshold, not its average value, so
they are scored on their crossings. Printing the average beside a crossing
limit would show a pass next to numbers that seem to contradict it (0.030
against a 0.020 bar) when the figure actually compared was 0.004.

## The noise the netlist declares is the noise the model gets

The netlist for this case says

```spice
vdd dd 0 dc {vcc} trnoise(0.02 1e-10 0 0)
```

That is a supply with random noise on it, set by the `trnoise` (transient
noise) settings. The first two numbers are the white-noise ones: an amplitude
of 20 mV rms, and a time step of 100 ps between new random values. The next
two, both zero here, would add flicker (1/f) noise.

A composed model that reads that line and then generates
`assign dd_v = 3.3;` has deleted a disturbance the design asked for. Every
later check then agrees about a circuit nobody is shipping. What the tool
generates instead, in
[`netlist_top.sv`](../../showcase/pll_cosim/netlist_top.sv):

```systemverilog
int unsigned dd_rng;
initial dd_rng = DD_SEED;
real dd_nw;   // white, sample-and-hold at the deck's NT
initial begin
  dd_nw = 0.0;
  forever begin
    #(DD_NOISE_DT_S * 1.0e15);
    dd_nw = DD_NOISE_RMS * __gauss(dd_rng);
  end
end
assign dd_v = ((dd_v_ext > 0.0) ? dd_v_ext : DD_NOM) + dd_nw;
```

The noise amplitude and the time step are the ones the netlist declares. The
supply can still be overridden from outside. The random generator starts from
a fixed seed (`DD_SEED`), so a rerun repeats exactly.

In a transient simulation of this netlist, that noise source causes 11.80 ps
rms of period jitter at the oscillator, ±5% over the two hundred cycles it was
measured on. That jitter figure is itself one random draw. A constant supply
produces no jitter at all.

### Measuring the jitter takes one step first

The jitter figure is measured for each design, never quoted from somewhere
else. To measure a block, the tool pulls it out of the netlist, and pulling
it out rebuilds every supply as a plain DC source, without the declared
noise. So the tool puts the declared noise back onto the block's own supply.
Without that step the measurement would describe a quieter circuit than the
one being modelled. The generated file records which source the number came
from.

The declared source is then carried into the composed model: a new random
value is taken at each of the source's own time steps and held until the
next. That reproduces the two properties that decide how much jitter a noise
source causes, its rms and its correlation time. The noise spectra of model
and SPICE agree at low frequency. They part company near 1/NT (NT is the time
step), because ngspice interpolates between its random values while the model
holds them flat.

### All seven fields of a `trnoise` declaration are read

Not just the two white-noise ones. Where a netlist declares flicker (1/f)
noise, the composed model carries it as a Voss–McCartney summation (a sum of
random sources updated at octave-spaced rates) across the octaves the run
spans. Where it declares random-telegraph noise (a signal that jumps between
two levels), the model carries it as a two-state Markov process with
exponentially distributed dwell times, using the capture and emission times
given. The Voss construction produces α = 1. The generated file records both
that and the exponent the netlist asked for, rather than quietly swapping one
for the other.

This PLL's netlist declares white noise only, which is why every figure here
shows white noise. Flicker noise dominates close-in phase noise, and a
netlist that declares it gets it in the model.

### Carrying the noise changes what a comparison means

The model run and the transistor run now each make their own random noise.
Two runs of the same circuit therefore differ by chance alone, and with a
fixed tolerance the verdict would depend on how long the run was. So each
node's limit is widened to allow for that run-to-run variation, by three
standard errors of the difference between two window means. The standard
error comes from how much the SPICE reference itself varies, not from the
declared amplitude, because how much noise reaches a node is a property of
the circuit. On `vout` that allowance was 0.189 of the 0.239 limit in this
run. The record carries both, so a reader can see how much of the limit was
earned by agreement and how much was allowance for noise, and that the
allowance is the part that moves between runs.

## Where the block works is measured, not assumed

The two output-buffer inverters sit in the clock path. Their job is to place
clock edges in time, and an average voltage error barely notices that. Both
pass an average-error comparison comfortably, yet their error at the single
worst instant is 99.9% of the full voltage swing. Those two facts do not
conflict. If the model's edge lands slightly late, then for that brief moment
the model sits at one supply rail while the real circuit sits at the other.
Averaged over time, the moment disappears. For a clock buffer, that moment is
exactly the behaviour being verified.

The tool sorts the two inverters by their measured DC curve. With 62% and 61%
of swept points within 5% of a rail, the curve is a switching
characteristic, not a smooth response. So they get scored on duty cycle
instead.

**The clock frequency they are scored at is measured too.** Where a block
operates is a property of the closed loop, and it exists only once the
digital side is attached. The same goes for the operating voltage range,
which the golden probe (the SPICE run that measures the expected values)
already measures. So the probe measures each net's switching rate alongside
its voltage range. The two inverter inputs come back at 399.7 and 399.8 MHz,
the 400 MHz this PLL locks to. Scored there, they pass at 0.316 and 0.326 pp
of duty cycle, against a 0.5 pp limit. The rms voltage error is reported
beside each one, 0.112 and 0.129 against the same 0.15 limit it was judged on
before, but it no longer decides the verdict.

The model form they are regenerated in has no delay line, so it cannot
represent the measured rise/fall skew: 0.584 and 0.657 pp of duty at that
clock. Both blocks measure below their own floor, so the skew partly cancels
rather than adding up. That makes the floor an upper bound on what the
simpler model form costs, not spare margin. The tool states this before
scoring, so a pass is not read as unqualified.

### A language model cannot supply that clock frequency

Asked five times about the same inverter with the same measurements, the
classifier (the language model that judges design intent) proposed clock
rates of 2 MHz, 765 MHz, 300 MHz, 10 GHz and 15 GHz. On the run these figures
come from, asked once per stage, it proposed 15 GHz for the first and 13 GHz
for the second. The lowest of those eight is two hundred times below where the
buffer runs. The highest is thirty-seven times above what the buffer's own
model can follow.

The measurement returns the same answer every run, and its answers for the
two stages agree to 0.04%, which no classifier run did. The rule is: design
intent from the language model, physical values from the circuit. The clock
rate looked like intent, but it is physics. See
[ai-and-measurement.md](../ai-and-measurement.md).

On what it is actually asked for, the classifier has been consistent: buffer,
clock stimulus and duty-cycle metric, on every run of both stages. That is a
judgement it can check against a measurement. What varied was the one number
it had no way to know.

### The pass/fail result names the metric it came from

Asking for the classifier does not guarantee it was used. Every duty-cycle
figure above comes from a run with the classifier reachable and consulted.
The same demonstration was also run deliberately with it *unreachable*, to
see what a reader would be shown in that case.

With the classifier unreachable, the same two blocks are driven by the
default chirp and judged on rms voltage, where they pass at 0.026 and 0.025
against a 0.15 limit. With it reachable they are driven by a clock at the rate
the golden probe measured and judged on duty, where they pass at 0.316 and
0.326 pp against a 0.5 pp limit, and the rms figure on that stimulus is 0.112
and 0.129. Three of the five blocks are unaffected either way, because their
routes involve no choice of stimulus.

The default chirp stimulus is kept, and that is a green result from a
measurement that cannot see the property in question, namely edge timing. The
two transcripts are otherwise alike and the command line is identical. So the
run records which figure each verdict was based on, and the demonstration
reports it from that record. **Asking for a check on the command line does not
prove that it ran.**

## Files worth opening

| Looking for | Open |
|---|---|
| an oscillator model, a frequency rather than a gain | [`ro_vco.sv`](../../showcase/pll_cosim/ro_vco.sv), with its 15-point measured tuning curve |
| a switched current model, per control state | [`cpump.sv`](../../showcase/pll_cosim/cpump.sv), one *I(V)* table per state, high-Z included |
| an RC state space taken from topology, nothing fitted | [`lpfilt.sv`](../../showcase/pll_cosim/lpfilt.sv) |
| a model pin-compatible with its subcircuit | [`ro_vco.sv`](../../showcase/pll_cosim/ro_vco.sv) -- module `ro_vco`, the `.subckt`'s own pins in its own order, so the netlist's `xvco` card instantiates it unchanged; the squared-up clock is an internal signal and `aout` carries the voltage |
| boundary work inside the model | [`cpump.sv`](../../showcase/pll_cosim/cpump.sv), carrying conductance out beside current because pump and filter form an algebraic loop, and reading the deck's two gate pins as the control its tables are indexed by |
| the composed system on the design's own testbench | [`netlist_top.sv`](../../showcase/pll_cosim/netlist_top.sv) with [`env/cosim/uvm_ms/`](../../showcase/pll_cosim/env/cosim/uvm_ms/) |

The system environment carries a period-jitter monitor at a 1 fs timescale.
Why that is reported with no pass/fail limit is in
[jitter.md](../jitter.md#the-system-level-figure-and-why-it-carries-no-limit).

That environment's own output is published, rather than only its sources:
[`showcase/uvm_ms_runs/pll_cosim/`](../../showcase/uvm_ms_runs/pll_cosim/) holds
a log per environment and a `SUMMARY.txt`. All four reached `$finish` with no
UVM errors -- the system one reporting 5 checks, 0 failed, 1 inconclusive over
116,012 boundary crossings, and 12.7022 ps rms period jitter over 1151
periods.

## Provenance of this deck

It is `examples/pll/pll_analog.cir` from
[ams-cosim](https://github.com/vrajeshprakhya/ams-cosim) with exactly one
change: the supply card `vdd dd 0 dc {vcc}` carries `trnoise(0.02 1e-10 0 0)`,
the operating condition the specification states, and the reason the PLL case
studies run on a noisy rail. Both PLL demos assert that card is present
before running anything. The RTL the loop closes around is the example's own,
published unchanged.
