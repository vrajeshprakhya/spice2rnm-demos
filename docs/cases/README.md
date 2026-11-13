# The case studies

Four circuits, easiest first, and the last of them run twice. Each is one
command. Every number on these pages came out of the shipped tool, and all of
it together took about an hour on a laptop.

| | Circuit | What it shows | Page |
|---|---|---|---|
| 1 | two-pole RC low-pass | the baseline: a verified model in under a minute, holding up on an input it has never seen | [01-two-pole-filter.md](01-two-pole-filter.md) |
| 2 | duty-cycle corrector | a block that defeats fixed-response modelling, verified on what it does to duty instead | [02-duty-cycle-corrector.md](02-duty-cycle-corrector.md) |
| 3 | phase interpolator | a block with no amplitude transfer at all, verified on edge position per code | [03-phase-interpolator.md](03-phase-interpolator.md) |
| 4 | phase-locked loop | three measuring problems in one netlist, composed and checked against the transistors | [04-pll-cosimulation.md](04-pll-cosimulation.md) |
| 4b | the same PLL | the same circuit with no SPICE in the loop at all | [05-pll-systemverilog-only.md](05-pll-systemverilog-only.md) |

The last two are the same circuit from opposite ends. Case 4 starts from a
co-simulation that already runs and uses it as the reference. Case 4b starts
where most designs actually are, with an analog netlist, some RTL, a
specification in English and nothing wiring them together.

## Results at a glance

| Case study | Environment | Checks | Failed |
|---|---|---|---|
| Filter | DC + AC | 49 + 15 | 0 |
| Duty corrector | DC + duty | 46 + 14 | 0 |
| Phase interpolator | phase per code | 9 | 0 |
| Phase-locked loop | SV–SPICE co-simulation vs SPICE | 5 + 4 | 0 |
| the same loop, SV only | UVM-MS loop env, derived/declared bands | 5 + 12 | 0 |

The first three case studies run end to end in under 16 minutes on a laptop.
That covers measuring the circuits, generating the models, both simulators,
and every generated environment. The PLL adds about 11 minutes more, most of
it spent measuring the ring oscillator's tuning curve (its frequency against
control voltage).

The SV-only variant takes its time for the same reason. On the run these
figures come from, the pipeline took 11 minutes with the loop closing
included, and running the four generated environments afterwards took another
11. The total moves between runs, because the oscillator's refinement passes
vary and because the machine is shared.

The SV-only run's twelve extra checks belong to the loop environment and
cover three windows. Its 5 per-block passes carry less weight than the 5 in
the row above, for the reason given on
[its own page](05-pll-systemverilog-only.md#what-this-result-does-not-carry).

## Two notes on the two counts of "5 of 5"

The co-simulation run and the SV-only run both report five blocks passing, and
the two fives are not worth the same. A clock buffer's verdict only means
something with the duty-cycle metric, and that metric needs the clock's
frequency, which only the co-simulation's golden probe can measure. The two
runs agree on the count and differ on what the count is worth.

## Running them yourself

Each case is one script in the repository root:

```sh
./demo_1_lpf.sh
DEMO_PAUSE=1 ./demo_2_dcc.sh    # pause between acts, for presenting live
```

[`../../run_all.sh`](../../run_all.sh) chains the first four.
`demo_4b_pll_nocosim.sh` is run on its own, because it costs about as long
again as demo 4. Prerequisites and path overrides are in the
[repository README](../../README.md).

The co-simulation case needs more installed than the others. Being the analog
half of a co-simulation, it needs the other half: the RTL, the DPI bridge,
and a *shared* libngspice, which is a different ngspice build from the
standalone binary the first three cases use. The script looks for each piece
before it does any work, and if one is missing it stops there and says which
piece and where to get it, rather than failing twelve minutes into a run.

## One case the whitepaper does not cover

[`../../showcase/ctle_sparams/`](../../showcase/ctle_sparams/) is a fifth
demonstration, added after the whitepaper build these pages quote. It is the
only case in the repository whose deliverable is a **measurement rather than
a model**: the differential transmission SDD21 of a CTLE equaliser, measured
from the transistors and from the shipped model and compared, with the port
match and the mode conversion measured and reported as *not modelled*. It is
described in [`../../showcase/README.md`](../../showcase/README.md) and run by
`demo_5_sparams_ctle.sh`.
