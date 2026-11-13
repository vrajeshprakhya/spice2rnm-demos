# Jitter: the one thing a score at an operating point cannot see

**Whitepaper** §8.3, and the jitter item in §13

Every check in [equivalence.md](equivalence.md) is *static*: it compares a
value at a fixed operating point. That suits most of what a model claims. It
is blind to one error that matters, though. **It cannot see what the model
does when the control or supply voltage is *moving*.**

## Two models that score identically and behave differently

An oscillator model has to decide when to place its next edge, and there are
two ways to do it.

- The **sampling** form reads the control voltage at the instant of the
  previous edge and schedules a whole half cycle from that single reading.
- The **integrating** form adds the control voltage up across the cycle as it
  changes, which is what the real circuit does.

Both forms use the *same* tuning curve. So a check that measures frequency at
fixed control voltages scores them identically, and in practice it passes
both.

Feed them the same *moving* control voltage and they come apart. On the
reference ring oscillator, with a control disturbance of 100 ps correlation
time, the sampling form produced **3.37×** the period jitter of the
transistors in SPICE.

The size of that gap is not fixed. It depends on how fast the disturbance
moves. The predicted ratio is √(T<sub>half</sub>/τ), where τ is the
disturbance's correlation time (roughly, how long it stays at one value) and
T<sub>half</sub> is the half period. For 1.25 ns against 100 ps that predicts
3.54, within 5% of the measured value above. A faster disturbance pushes the
two forms further apart, so a ratio quoted without its τ says less than it
looks like it does.

## So the tool tests the moving case directly

A known disturbance is injected in SPICE at several amplitudes. Then the exact
disturbance waveform *that ngspice actually solved* is replayed into the
model, sample for sample.

**The replaying is the part that matters.** Give the model its own separate
random noise of the same size, and the check ends up comparing two unrelated
random sequences, whose agreement depends more on how long the run was than
on the model. Replaying the same waveform tests the thing worth testing: how
a disturbance turns into jitter.

Both of the oscillator's inputs are tested, not just the obvious one. On the
reference ring, the supply voltage moves the frequency by 450.6 MHz/V: about
as much as the control input does, and in the opposite direction. A model with
no supply input could not show what a supply droop does at all. The overall
verdict is the worse of the two paths.

Each row gives the rms period jitter of the circuit and of the model, and the
model-to-circuit ratio. A ratio of 1 means perfect agreement.

| Path | Injected | Circuit | Model | Ratio |
|---|---|---:|---:|---:|
| either | none (floor) | 0.051 ps | 0.000 ps | no limit |
| control | 5 mV rms | 2.396 ps | 2.352 ps | 0.981 |
| | 20 mV rms | 8.743 ps | 8.690 ps | 0.994 |
| | 50 mV rms | 26.719 ps | 25.618 ps | 0.959 |
| supply | 5 mV rms | 2.808 ps | 2.640 ps | 0.940 |
| | 20 mV rms | 11.617 ps | 12.139 ps | 1.045 |
| | 50 mV rms | 28.422 ps | 27.656 ps | 0.973 |

**Each ratio is one random sample**, not a fixed property of the model. Every
injection uses a fresh random noise waveform, and an rms measured over two
hundred cycles carries a sampling uncertainty of about 5% either way. That is
why the same six points on the previous run read 0.987, 0.946, 0.925 and
0.896, 0.953, 0.970. That spread is why the pass/fail limit is 0.25 rather
than something that looks stricter. A tolerance tighter than the
measurement's own uncertainty would fail correct models, at a rate set by how
long the run happened to be.

**The floor row is measured, but reported for information with no limit.**
With nothing injected at all, the reference still reports about 54 fs of
jitter. That figure is the precision with which the edge-finder locates a
threshold crossing. It is not anything the circuit did. Asking the model to
reproduce it would be asking it to reproduce a measurement artefact. Instead
it is the floor every other amplitude has to clear before its result counts.

## That agreement was not obtained by fitting anything

Simple physics predicts it. Take the supply path, where the sensitivity is
measured separately. If the disturbance held still for a whole cycle, then
450.6 MHz/V on a 2.509 ns period would predict 14.18 ps of period jitter for
5 mV rms. The circuit gives 2.797 ps, a ratio of 0.197.

The reason is that the oscillator averages a fast disturbance out over its own
period. Averaging about T/τ independent pieces of noise shrinks the effect by
√(τ/T) = √(100.3 ps / 2509 ps) = 0.200, which is what the circuit shows.

This holds across the whole tenfold range of amplitudes, not just at one
point: the ratio is 0.197, 0.223 and 0.203 at the three amplitudes checked. An
oscillator that did not average its input would sit at 1, five times higher.
All three points land within 12% of a prediction with no fitted parameters,
and each carries the same few per cent of sampling uncertainty as the ratios
above. The integrating model reproduces this because it integrates. The
sampling model does not.

## The tool decides for itself whether this check is worth running

For most designs the honest answer is no, and the check costs a quarter of an
hour. Two things can say yes.

**The first is the design's own closed-loop behaviour, measured.** The tool
measures how far the control voltage moves within one oscillator period,
converts that into period movement using the tuning curve's slope, and
compares it with what the reference measurement can resolve. On this PLL the
answer is no, and it comes with numbers. On a run where this was the deciding
input, the control moved 12.18 µV rms per 2.503 ns period. That is worth
0.0288 ps against a 0.0521 ps floor, or 0.55× what the reference can resolve.
A loop filter holds its control voltage still. That is its whole purpose.

**The second is the netlist**, and it is what triggered the sweep above. This
netlist declares 20 mV rms of noise on the ring's supply, and a design that
writes noise into its own netlist is asking for noise to be simulated. The
rule matches on the net name, not the source name, because block extraction
rebuilds every supply as a plain DC source. The extracted fragment carries
`VBIAS2 dd 0 DC 3.3`, where the top level wrote
`vdd dd 0 dc {vcc} trnoise(...)`. The net name survives extraction. The
source name does not.

**There is no flag to force the check**, because asking for a check is not
evidence that it is needed. Where the tool has no closed-loop evidence either
way, it runs the check rather than skipping it. Having no evidence that a
check is needed is not the same as deciding it is not.

### What the sweep measures, and what it does not

The sweep drives the ring oscillator on its own, on the fragment extracted
for measuring it. That is the right scope for its question: does this model
turn a disturbance into jitter correctly? It is a different question from what
the PLL does with a disturbance. Inside the loop, the filter holds the control
voltage still, which is exactly why the closed-loop test above says no. These
numbers come from driving the block directly, with nothing holding it. **So
the supply rows say nothing about this PLL's supply rejection. They say
something about the model.**

## Two different jitter jobs

The tool does both, and they are not the same work.

### Jitter transfer: checked, with a pass/fail limit

*Jitter transfer* is what the model does with a disturbance you hand it. The
disturbance is injected into the transistors in SPICE, the very same
disturbance is replayed into the model, and the period jitter of the two is
compared. It is done on the control input and on the supply. The table above
is the result: six points over a tenfold range, worst ratio 0.940 against a
0.25 tolerance.

Nobody asked for this check. The pipeline ran it by itself, because the
netlist declares noise on a net the ring oscillator is wired to. It is a real
check with a real verdict, and it fails a model whose transfer is wrong.

### The oscillator's own noise: measured, and shipped set to zero

The oscillator's own noise is measured through its impulse sensitivity
function (ISF), Γ(φ). That is a mouthful for a simple idea. Give the
oscillator a tiny kick of charge at point φ of its cycle and see how far the
kick shifts its phase for good. Kick it at one point and almost nothing
happens. Kick it at another and the shift is large. Γ(φ) is that sensitivity,
point by point around the cycle. The pipeline measures it without being asked:
it injects a narrow charge pulse at each phase and measures the lasting shift.

On the reference ring, the rms value Γ<sub>rms</sub> comes out at
4.04 × 10¹² rad/C from the automated sweep, against 4.33 × 10¹² measured by
hand. The two agree to 7%. Γ changes sign across the cycle, as a ring
oscillator's has to, and halves when the injected charge halves.

Multiply Γ<sub>rms</sub> by a device noise density and you get a jitter: 0.236
to 0.578 ps rms here, or −114.5 to −106.7 dBc/Hz at 1 MHz. It comes as a range
because two of its inputs are themselves ranges: the transistor channel-noise
factor, and the way the noise densities of the individual nodes add up. **The
model carries this jitter as a parameter, shipped set to zero.** The figure is
worked out from the measured ISF rather than compared against a SPICE
transient, because ngspice does not simulate device noise in a transient run.

> The method is Hajimiri, Limotyrakis and Lee, *Jitter and Phase Noise in Ring
> Oscillators*, IEEE JSSC 34(6), June 1999. Two details decide whether it
> works, and getting either wrong returns a plausible wrong answer rather
> than an error, so the tool enforces both. First, the pulse goes in
> differentially where the circuit is differential. Injected into one node of
> a differential ring it is mostly common mode, which the ring is built to
> reject, and the measurement then just reads its own noise floor however big
> the pulse. Second, linearity is checked at the phase where the ring is most
> sensitive, not at a convenient one. The same charge that moves the phase by
> 0.04 ps where the ring barely responds moves it by 52 ps at the peak.

## Driven blocks jitter differently, and the models follow suit

An oscillator times each edge from its own previous edge. Its phase therefore
wanders off on a random walk, and the timing error piles up. A buffer or a lag
block times its output from an *input* event instead. Each trip through the
block picks up its own independent random delay, and nothing piles up.

On that basis, the scheduled-lag models take a synchronous-jitter figure and
nudge the input-to-output delay once per trip through the block. **You supply
that figure.** It is not measured, and it cannot be: a SPICE transient of a
netlist that declares no noise holds no delay variation to measure. The
generated file says so. It also states the fixed extra latency the nudging
costs, because the model's delay line can only look backwards in time, so an
edge can be made early only relative to a delay that is already there.

> The distinction and both implementations are Kundert's, in *Modeling and
> Simulation of Jitter in Phase-Locked Loops*, AACD 1997. This model follows
> four of his points. Driven systems jitter without accumulating, while
> autonomous ones (free-running oscillators) have a phase difference that is
> "a random walk that is not bounded". The metric for both is *J* = σ(T), the
> standard deviation of one period. Driven jitter is modelled by "randomly
> dithering the delay argument ... on every output transition". And with *N*
> updates per period, the per-update dither scales by √*N*, which is 1.414 for
> the two updates this model uses.
>
> Each point was checked. Asked for 1% rms period jitter, the model produced
> 0.9998%. Its scaling constant is the √2 his listing specifies. Over 30,000
> cycles, the variance of the accumulated deviation grew linearly with cycle
> count, at 1.004 ± 0.026 of the *kJ*² his random walk requires.
>
> One setting is refused. At one sub-step per half cycle the scheduler cannot
> resolve a randomised threshold, so the model turns that setting down rather
> than report 39.6% jitter when 1% was asked for.

## Edge jitter, reported with no limit

*Edge jitter* is measured wherever the transistors in SPICE have clock edges.
On the reference PLL's two clock-path buffers it is 3.98 ps and 3.60 ps. It is
printed next to the skew, because jitter and skew go wrong in different ways.
It is reported for information, with no pass/fail limit, because there is no
agreed threshold for it. Inventing one from a single design would be worse
than just showing the number.

### The system-level figure, and why it carries no limit

Here the reason is the measurement rather than the model. The system-level
equivalence check's boundary log is sampled every 100 ps. The composed model's
output crosses its threshold between samples, so a crossing can only be
placed to the nearest sample. Calling that jitter would be measuring the
sampling grid, not the circuit.

The generated UVM-MS environment has a monitor without that problem. It
reacts to each change of the signal instead of sampling on a clock. It is
compiled with a `1fs` timescale while the rest of the environment stays at
`1ps`, which costs nothing elsewhere because SystemVerilog sets timescale per
module. Run that environment on the composed PLL and it reports 12.78 ps rms
period jitter over 1151 periods at the boundary. Over 116,012 boundary
crossings, none of its system checks failed and one was inconclusive. The
total number of checks is not quoted because it varies: one check exists only
when the transistors settled measurably, which under a noisy supply they may
or may not do.

That 12.78 ps is for information only too, for a specific reason. **A PLL
suppresses its own oscillator's jitter inside the loop bandwidth.** A figure
measured at the PLL boundary is therefore not the oscillator's own jitter, and
nobody should expect the two to agree. The 11.80 ps that this netlist's
declared supply noise produces at `ro_vco` is a different measurement of a
different quantity. Both figures come from the same run, which earlier
versions of the whitepaper could not say. The gap between them is 17% here,
and has been 16% and 20% on other runs of this same netlist. Each is one run's
draw from a random spread, and neither is evidence about the other.

## Where this sits against published practice

The gap named above, no intrinsic device noise in the model, is one published
practice shares. Analog Devices' production RNM suite for a GHz transceiver
validates its PLL on lock time and frequency error, the same quantities
checked in [equivalence.md](equivalence.md). It says that "model validation
remains an area for improvement in the real number modeling flow", and lists
frequency-domain performance as future work.

> J. Dudek, J. Nekl and K. O'Donoghue (Analog Devices), *Real Number Modeling
> of RF Circuits*, DVCon proceedings,
> <https://dvcon-proceedings.org/wp-content/uploads/real-number-modeling-of-rf-circuits.pdf>.
> The paper notes that because RNMs exist to enable system-level testing, "the
> requirements for model validation are greatly relaxed in this environment".
