# What the equivalence check compares

**Whitepaper** §7.1 and §8

Every model in the case studies was checked the same way. The generated
SystemVerilog goes into a digital simulator and gets an input signal. The
transistors in SPICE get the very same input. The two outputs are then lined
up in time and compared point by point. Both traces are saved, so anyone can
open the run's own folder and work the number out again.

Two things about this check matter more than the numbers it produces.

## It tests the file you are actually handed

Some tools report a weaker number: how well the fitted equations matched the
measurements they were fitted to. That number never opens the generated file,
so it would look identical even if the file had been written out wrongly.

This check loads the generated file into a simulator and runs it, so a
code-generation bug makes it fail.

## Each block is judged on its own job

One error figure for every block would miss the point on most of them. An
average voltage error cannot see where a clock edge lands, and an
oscillator's frequency has no voltage error to measure in the first place.

| If the block | then compare | and score it as |
|---|---|---|
| passes a signal through | the output waveform, on a sweep and on a second, unrelated input | the error, against how far the output itself moves |
| drives a clock | where the edges land, at the rate measured in use | duty error, in percentage points |
| moves an edge per setting | the crossing time at every setting | picoseconds, plus step size and evenness |
| oscillates | the output frequency, as the control voltage varies | a percentage of that frequency |
| switches a current | the current it drives, in each switch position | a percentage, for each position |
| is passive R/C | the output's response to a current pushed into it | the error, against how far the output moves |

The fourth row cannot be scored like the first. Two oscillators at the same
frequency still drift apart in phase, so subtracting their waveforms would
score a perfect model as completely wrong. [routes.md](routes.md) works that
through.

Every verdict records which row of this table it came from. So months later
you can still tell which number decided the result, and which numbers were
only noted beside it.

A check that does not apply to a given run is reported as not applicable,
with the reason. It is never quietly counted as a pass.

## What keeps a figure from flattering itself

**Some measurements are held back.** When a block is measured at many points,
a share of those points is kept out of the model-building and used only for
scoring. So the headline figure is not the fit marking its own homework. The
charge pump in the PLL reports 0.549% error on held-back points. The ring
oscillator reports its held-back frequency error directly.

**An input the model has never seen.** The filter is built from a frequency
sweep. It is then tested with a pseudo-random bit sequence it was never shown
(0.0097). A model that had merely memorised the data it was built from would
be caught there.

**The report says what range the answer covers.** A comparison proves nothing
about conditions it never tested, so the report states the conditions it did
test. The ring oscillator is the clearest case, and the honest answer there is
two numbers. Inside the control-voltage band the loop actually uses, its
held-back frequency error is 0.024%. Out at the far edge of the wider measured
range, where the tuning curve bends hardest and the loop never goes, the error
reaches 4.987%. Both numbers get printed, and both come from
[the SV-only run](cases/05-pll-systemverilog-only.md). The co-simulated run of
the same block, whose band the golden probe measures rather than the
specification declaring it, reports 0.003% and 5.348%. The verdict is taken in
the band that matters, and the less flattering number is printed rather than
quietly dropped.

**Known limits of the model shape are priced in advance.** Sometimes the
chosen model shape simply cannot do something the circuit does. When that
happens, the cost is stated up front, in the same units as the verdict. The
inverter timing asymmetry in the PLL is an example, quoted as duty error at
the clock rate in use. A pass is then read against that floor, not taken as a
clean win.

## Blocks, and then the system

The table above scores blocks one at a time. Wiring blocks together raises a
further question: errors that are small in each block need not stay small
once everything is connected. Three levels of check answer it.

**First level: the netlist alone.** The assembled model is driven at the
external pins of the design. Its output is compared against the full
transistor circuit in SPICE, driven the same way.

**Second level: an existing SV–SPICE co-simulation.** This level applies when
you hand the tool a co-simulation set-up. The design's own testbench is run
twice. Once with the generated models as the analog half, once with the
transistors. Nothing else changes. The digital logic, the limits it checks
against and the pass/fail rules are byte-for-byte identical in both runs. Only
the small piece of code joining the two halves is swapped out. That makes the
two runs comparable signal by signal: 4 signals crossing between the halves,
0 failed, the control voltage agreeing to 4.158 mV on a rail carrying 20 mV
rms of declared noise, and both versions locking to the same frequency.
[Case study 4](cases/04-pll-cosimulation.md) reports this level.

**Third level: SystemVerilog only.** Most designs have no co-simulation
set-up. What they have is an analog netlist, some RTL, and nothing joining the
two. Here the models are composed and the customer's own RTL is wired around
them in SystemVerilog, with no bridge and no SPICE anywhere in the loop. The
question is whether the assembled design does its job. A full UVM-MS
environment drives it and checks it against two things: the specification,
*and* what this run measured. The oscillator's own tuning curve, for instance,
says which control voltage ought to give the target frequency. A loop that
hits the right frequency at the wrong control voltage is therefore caught, not
counted as a pass. [Case study 4b](cases/05-pll-systemverilog-only.md) runs
the same PLL this way. It locks to −0.0005% of its reference, with the control
voltage 0.89 mV from where the measured tuning curve puts it. This is
deliberately a weaker claim than the second level makes, because there are no
transistors in the run to disagree with it.

One error none of these three levels can see is the subject of
[jitter.md](jitter.md): what the model does when the control or supply voltage
is *moving*.

## What the equivalence folders hold

Every case study publishes an `equivalence/` directory. It holds what the
check ran, what it found, and a list (`MANIFEST.txt`) of the large files kept
out of the repository.

| Case | Scored on | Published verdict |
|---|---|---|
| Filter | rms voltage | 0.0290 against 0.15 |
| Duty corrector | rms voltage | 0.0769 against 0.15 |
| Phase interpolator | phase per code | worst 1.832 ps at code 2, tolerance 6.251 ps |
| Phase-locked loop | five routes, then the whole system | five block verdicts, and the system over 116,018 samples |

Start with two files. `equivalence/verdict.txt` sums up the check and its
conclusion, one line per route: the metric, the worst point, the pass/fail
limit, and the verdict. Beside it, the case's `result.json` is the full record
that line was taken from. It records what was driven, what was compared, over
how many points, and every warning raised along the way.

Each folder carries three things. First, `verdict.txt`, which the tool copies
out of that run's own `result.json` rather than retyping, so a number here
cannot disagree with the run that produced it. Second, the simulator and SPICE
logs, which show what actually ran. Third, a comparison table with one row per
measured point. The phase interpolator's `phase_compare.csv`, for instance,
has nine rows, one per control code: the measured delay, the model's delay,
and the error. The PLL's `rc_compare.csv` is the loop filter's response to an
injected current, sample by sample.

### Why some files are listed instead of published

Some output files are large, easy to regenerate, and add little for a reader,
so they are not committed. Git keeps every committed file in the repository's
history forever, so anyone who clones it downloads them, even after they have
been deleted. Instead, `MANIFEST.txt` names each such file with its exact size
and the command that recreates it. You can see what exists and how big it is,
without every future clone having to carry it.

The large files all come from the waveform routes. Those write one row per
simulator timestep, not one per measured point. The filter's aligned
comparison is 18.6 MB and its generated testbench 18 MB. The duty corrector's
comparison is 2.8 MB. The PLL is the bulk of it: its co-simulation waveform
file alone is 202.8 MB, two thirds of everything the five cases produce.

Together that comes to nearly 296 MB, and
[`../showcase/refresh.sh`](../showcase/refresh.sh) regenerates all of it in
half an hour. Committing it would leave the repository permanently heavy for
no lasting gain. What is published comes to 1.4 MB. Of that, the SV-only PLL
is 546 kB: four environments, the loop harness, the customer's RTL and both
specifications.

**The rule goes by file size, not by file name.** A comparison table small
enough to read is evidence. One large enough to be a waveform is a trace.
Routes differ in which they produce: a network compared point by point writes
a table, while a waveform compared sample by sample writes a trace. So the
rule has to look at the file itself, not at what it is called.

The repository leaves two more things out on purpose. One is the spice2rnm
tool itself: the product is licensed separately, and this repository is its
evidence. The other is the build litter from the runs, meaning scratch files
from the measuring, compiled simulator objects and DPI shims. `refresh.sh`
filters those out, so the showcase holds what a user would keep, not
everything a run leaves behind.
