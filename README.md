# spice2rnm demos

Five walkthroughs of **spice2rnm**, Veylon Systems' netlist-to-verified-model
pipeline for mixed-signal verification -- each built around one circuit and
one question.

| | circuit | what it shows |
|---|---|---|
| `demo_1_lpf.sh` | two-pole RC low-pass | the baseline: verified model in under a minute, holding up on binary data, with a running UVM-MS environment |
| `demo_2_dcc.sh` | duty-cycle corrector | level-dependent dynamics: a block that defeats fixed-response modelling, verified by what it does to duty |
| `demo_3_pi.sh` | phase interpolator | a block with no amplitude transfer at all, verified by phase per code |
| `demo_4_pll.sh` | phase-locked loop | three characterisation problems in one netlist, composed and checked against the transistors on the design's own co-simulation testbench |
| `demo_4b_pll_nocosim.sh` | the same PLL | the same circuit with no co-simulation anywhere: operating bands declared from the specification instead of probed, and the loop closed around the customer's RTL in pure SystemVerilog |

The last two are the same circuit from opposite ends. Demo 4 starts from a
co-simulation that already runs and uses it as the reference. Demo 4b starts
where most designs actually are -- an analog netlist, some RTL, a
specification in English, and nothing wiring them together -- and needs no
bridge, no shared libngspice and no testbench spanning the two halves.

The generated artifacts themselves — models, environments, evidence — are
committed under [`showcase/`](showcase/), and the whitepaper under
[`whitepaper/`](whitepaper/).

Run one:

```sh
./demo_1_lpf.sh
DEMO_PAUSE=1 ./demo_2_dcc.sh    # pause between acts, for presenting live
```

`DEMO_PAUSE=1` waits for Enter between acts. Everything else runs unattended.

## What each demo prints is measured

No number in these scripts is quoted from memory. The pipeline output, the fit
coefficients, the equivalence score and the UVM-MS scoreboard summaries are all
read from the run happening in front of you — demo 1's PRBS score is captured
from its own harness and echoed in the summary, and demo 2 greps the generated
`.sv` so the audience reads the coefficients off the actual file.

Expect roughly one minute for demo 1 and three for demo 2. The two PLL demos
are much longer -- most of it measuring the ring's tuning curve one point at
a time -- and each reports how long it took.

## Prerequisites

These are not vendored, and the demos will exit early naming whatever is
missing. Override any path without editing the scripts:

```sh
S2R=/path/to/spice2rnm NGSPICE=/path/to/ngspice XEZIM=/path/to/xezim ./demo_1_lpf.sh
```

| | default | notes |
|---|---|---|
| `S2R` | `~/spice2rnm` | the pipeline, plus the netlists in `work/` |
| `NGSPICE` | `~/ngspice-install/bin/ngspice` | stock ngspice; the netlists are PDK-free LEVEL=3 |
| `XEZIM` | `~/xezim/target/release/xezim` | used as both compiler and runtime |

Demo 1's sixth act additionally needs the Accellera UVM-MS library, and a UVM
source tree if yours is not in the default location:

```sh
UVM_MS_LIB=~/uvm_ms_demo/ms ./demo_1_lpf.sh
```

The generated environment runs on xezim in a single invocation --- it compiles
and simulates UVM, the §6.6.7 nettypes and the proxy's out-of-module references
together, so there is no separate elaborate step and no second simulator to
install.

## Layout

```
demo_1_lpf.sh  demo_2_dcc.sh  demo_3_pi.sh
demo_4_pll.sh  demo_4b_pll_nocosim.sh
netlists/
  rc_lpf2.cir    the two-pole filter: demo 1's input
  dcc.cir        the duty-cycle corrector: demo 2
  pi_therm.cir   the phase interpolator: demo 3
  pll_analog.cir the PLL deck demos 4 and 4b run -- ams-cosim's example
                 plus the 20 mV supply-noise card it is run with
harness/
  prbs_vcd.py    PRBS through the LPF model, scored and dumped to VCD
  demo_dcc.py    threshold sweep -> the corrector's actuator characteristic
  dcc_vcd.py     clock in / clock out, SPICE and model on one set of axes
  demo_pi.py     per-code phase measurement across the interpolator
  pll_loop.json  how demo 4b's loop is wired: topology only, no electrical sense
specs/
  rc_lpf2_spec.md  the filter's specification, in English
  dcc_spec.md      the duty-cycle corrector's -- demo 2 reads it
  pll_spec.md      the PLL's -- demo 4b's third input
```

The harness scripts write under `~/s2r_runs/` and are called by the demos
through `$HARNESS`, so the tree relocates as a unit.

## Waveforms

Several acts emit VCDs worth opening:

```sh
gtkwave ~/s2r_runs/lpf2_vcd/tb_prbs.vcd
gtkwave ~/s2r_runs/dcc2_vcd/tb_dcc.vcd
```

Reals render as decimal numbers until you tell GTKWave otherwise. For each of
`spice_ref`, `out_val` and `err`: right-click → Data Format → Analog →
Interpolated. `err` on its own with autoscale is where the residual becomes
visible.
