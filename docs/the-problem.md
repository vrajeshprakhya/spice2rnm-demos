# The problem, and what one command gives you

## Why a model is wanted at all

An analog block is slow to simulate. SPICE has to solve the physics of every
transistor in it. A real-number model is the shortcut: it takes the input
number, does a little ordinary arithmetic, and hands back the output number.
No physics, no transistors. That lets it run in a normal digital simulator,
right beside the chip's logic, fast enough to sit in a full regression suite.

## Why that is hard to keep

A model has to be both fast and accurate, and the two pull against each
other. Fast, or it cannot run in a digital regression suite at all. Accurate,
or passing its tests means nothing.

Hand-written models drift away from the circuits they stand for, and nothing
announces the drift. The model still compiles. It still simulates. It still
passes its tests. It has simply stopped describing the circuit.

The usual safeguard is a hand-written testbench, and it has the same problem
one level up. A person decides what to check and how close counts as close
enough, and those decisions are rarely written down next to the numbers they
produced. When the circuit changes, the model, the testbench and the
tolerances all need revisiting by hand. In practice that does not happen.

So the writing is the catch. Someone has to build the model, keep it in step
with the circuit as the circuit changes, and show the team that it still
matches. The first two jobs are slow. The third one usually never happens at
all.

**spice2rnm regenerates all three from the netlist whenever you ask.** The
model, the environment that checks it and the evidence all come out of the
same command. So they cannot quietly fall out of step with the circuit, or
with each other.

## What you give it

A SPICE netlist, flat or with subcircuits. Optionally, a plain-language
specification as well, and an existing model library whose conventions the
tool should follow. You do not have to label ports, supply a model template
or write a testbench.

```sh
spice2rnm dcc.cir --emit-uvm-ms --spec dcc_spec.md
```

You do not name the ports. The tool finds them in the netlist. The supplies
carry only a DC level. The input is the node driven by the one source that
carries a transient waveform or an AC magnitude. On that netlist the node is
`clk`.

Finding the output is a harder problem, because the wiring alone does not say
which node you care about. The netlist's own `.save`, `.print` or `.probe`
statement does say it: that is the author naming the signal the netlist
exists to show. When a netlist has one, the tool takes the output from it.
When it has none, the tool guesses the output from the node names. Either way
the run reports which of the two it did, so you can tell a declared output
from a guessed one.

Four routes never guess: the ones that measure the edge, frequency or current
of one particular node. For those, you must name the output.

## What you get back

### A SystemVerilog real-number model

The tool picks the model's structure to match the block's measured behaviour.
That includes blocks whose speed changes with signal level, where any
fixed-response model is wrong over most of its range. See
[cases/02-duty-cycle-corrector.md](cases/02-duty-cycle-corrector.md) for a
block exactly like that.

The model has `wreal` ports, so it connects straight into an RNM library
alongside the models already there. The model itself connects. There is no
wrapper around it.

That choice affects function, not just style. A `real` port is a *variable*,
and a variable takes exactly one driver. Nothing else can share the node, and
a bridge cannot attach without a converter module in between. A `wreal` port
is a *net*, so several drivers can combine on it: an offset source, a noise
injector, a second bridge. The model then drops into a library with nothing
standing between it and the nets it is wired to.

There is one real cost. `wreal` comes from Verilog-AMS, not IEEE 1800, so the
model compiles only on simulators that support it, and everything that
instantiates the model inherits that requirement. For a flow without `wreal`,
`--model-ports real` generates the same model with variable ports, and it
depends on no package, no nettype and no language extension.
`--model-ports house` instead gives the model your own library's nettype
(see [joining-a-model-library.md](joining-a-model-library.md)).

The arithmetic is identical in every case. Only the port declarations differ.
One detail: a net cannot be assigned inside procedural code, so a model with
net ports drives its output through a single continuous assignment. We
measured whether that matters. It does not. The filter scores
`rms_error_norm` 0.029008790476737805 against SPICE with either port type,
identical to every digit.

### A UVM-MS verification environment

It follows the Accellera UVM-MS specification and is built on IEEE 1800, not
on Verilog-AMS.

Analog values travel on *user-defined nettypes* (IEEE 1800-2017 §6.6.7). The
generated package declares the nettype together with a generated resolution
function, `sum_res`, which adds up what all the drivers contribute. So when
several drivers share a net (an offset source, a noise injector, a second
bridge), the nettype combines them, with no hand-edited testbench code.

The environment instantiates the model itself, not a copy behind a wrapper,
so the checks cover exactly what ships. The environment's own structure is
IEEE 1800 throughout: the nettype, the resolution function and the
`interconnect` ports. The model it drives has `wreal` ports, though, so
running it does need a simulator that supports `wreal`.

Bridge and wrapper ports are `interconnect` (§6.6.8), so they take on the
testbench's nettype instead of naming one. And the scoreboard's golden values
are SPICE measurements of your circuit.

### Equivalence evidence

The circuit and the model get identical inputs. Their outputs are then
compared in the way that matters for that block: waveform error for blocks on
the signal path, edge position for blocks on the clock path. The aligned
waveforms are saved, so any verdict can be worked out again from its own run
directory. [equivalence.md](equivalence.md) has the detail.

## Results on five circuits

One command each. All five together took about an hour on a laptop, on
open-source simulators.

| Circuit | What is compared | Worst vs pass/fail limit | Environment |
|---|---|---|---|
| two-pole filter | waveform, unseen input | 0.0097 vs 0.15 | 64 checks, 0 failed |
| duty-cycle corrector | where its edges land | 0.428 vs 1.0 pp | 60 checks, 0 failed |
| phase interpolator | edge position per code | 1.83 vs 6.25 ps | 9 checks, 0 failed |
| PLL, SV–SPICE co-sim | system vs SPICE circuit | 4.158 mV, 47% of limit | 5 blocks, 0 failed |
| PLL, SV only | loop closed in SV alone | locked, −0.0005% | 12 checks, 0 failed |

Each row has its own page under [cases/](cases/).

## Why a passing result here is worth believing

Three rules hold throughout.

- The expected answers come from SPICE, never from the model. A test cannot
  pass by agreeing with itself.
- Every environment is shown to be able to fail. The tool breaks the model on
  purpose, confirms the test fails, and measures the smallest break the test
  still catches.
- Each block is checked on its own job: a filter on its frequency response, a
  clock buffer on its edges, an oscillator on its frequency. A check that does
  not apply to a block is reported as "not applicable", never counted as a
  pass.

[trusting-a-testbench.md](trusting-a-testbench.md) is the long version, with
the fault sweep that measures the second rule.

## Where the evidence is

Every model, environment and verdict is published exactly as the tool wrote
it, under [`../showcase/`](../showcase/). One command regenerates all of it.
The outputs are plain IEEE 1800 SystemVerilog with no vendor dependence. Here
they ran on ngspice and on the open-source simulator
[xezim](https://github.com/vrajeshprakhya/xezim), and they will run on the
simulators your flow already uses.

An optional plain-language specification supplies what no netlist can: the
block's intended operating range, and the criteria it has to meet. See
[`../specs/reading-a-specification.md`](../specs/reading-a-specification.md).
