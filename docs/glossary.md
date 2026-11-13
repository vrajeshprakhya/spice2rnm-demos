# Terms used in these pages

**Real-number model (RNM).** A SystemVerilog model of an analog block. It
works out output values from input values with ordinary arithmetic, so it
runs in a digital simulator.

**Netlist.** The SPICE description of a circuit: what parts it has and how
they connect. Older SPICE usage calls it a *deck*, and the tool's own
generated files still use that word.

**The transistors.** Short for the transistor-level circuit in SPICE (here,
ngspice): the real circuit, simulated in full. Every model is compared
against it. These pages say "the transistors" throughout.

**SV–SPICE co-simulation.** One simulation with a foot in each camp. The
design's digital RTL runs in the SystemVerilog simulator while its analog
part runs as the transistors in SPICE, and a bridge passes signals between
the two. "Co-simulation" always means that.

**SV-only system simulation.** Also "SystemVerilog only". The design's RTL
and the generated models of its analog blocks all run in the SystemVerilog
simulator. No SPICE anywhere.

**Generated.** Written as output by spice2rnm. A file "not generated" is one
the tool deliberately does not write.

**Equivalence check.** Giving the circuit (in SPICE) and the model the same
input, and comparing what comes out. See [equivalence.md](equivalence.md).

**Golden value.** An expected value in a testbench. It is measured from the
circuit in SPICE, never taken from the model.

**Route.** The measuring method the tool picks for a block: say, measuring a
filter's frequency response, or an oscillator's frequency against its control
voltage (its tuning curve). See [routes.md](routes.md).

**Bar.** Short for the pass/fail limit a result is compared against.

**Verdict.** The outcome of a check: pass or fail.

**Reported for information.** A number shown for information, with no
pass/fail limit applied to it.

**rms.** Root mean square: the standard way of measuring the size of a noise
signal or an error.

**pp.** Percentage points (of duty cycle, for example).

**Random sample, fixed random seed.** A simulation with noise in it gives a
different answer each run, so one run's answer is one random sample of the
possible answers. Fixing the random seed makes the random number generator
repeat itself, so a rerun gives the same answer.

**White and flicker noise.** White noise has equal power at all frequencies.
Flicker (or 1/f) noise gets stronger towards low frequencies.

**Jitter.** Variation in when clock edges arrive. *Period jitter* is the
variation in the time from one edge to the next. See [jitter.md](jitter.md).

**Composed model.** The individual block models wired together into a model
of the whole circuit.

**UVM-MS.** Accellera's Universal Verification Methodology for mixed-signal
designs, built on IEEE 1800 SystemVerilog.

**`wreal`, nettype.** Two ways of declaring nets that carry analog (real)
values in SystemVerilog. `wreal` comes from Verilog-AMS; a user-defined
nettype is the IEEE 1800 equivalent. See
[joining-a-model-library.md](joining-a-model-library.md).

**`MANIFEST.txt`.** The list of large output files that are not stored in the
repository. For each one it gives the size and the command that recreates it.
Such a file is "listed in `MANIFEST.txt`".

## Two terms the case studies need

**One LSB** (least significant bit) is one step of a control code. In the
phase interpolator the nine codes span 500.1 ps in eight steps, so one LSB is
62.51 ps, and that average step is the natural unit for everything else about
that block.

**DNL** (differential non-linearity) is how far an individual step sits from
that average.

## Two terms the stimulus discussion needs

**Chirp.** A single sine wave whose frequency slides steadily upward during
the run, like a slide whistle. One run therefore exercises the block at every
frequency in the band, which is why it is the default stimulus: it is the
cheapest way to see a whole frequency response in one transient simulation.

**PRBS** (pseudo-random bit sequence). A square wave that jumps between two
levels on a pattern that looks random but comes from a shift register, so it
repeats run to run. Sharp edges, energy spread broadly across the band,
nothing like a smooth swept tone. The filter model is *built* from a chirp and
then *tested* with a PRBS, so the PRBS score is the one that rules out a model
having merely memorised the stimulus it was fitted to.
