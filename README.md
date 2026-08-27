# spice2rnm demos

Three customer-facing walkthroughs of the SPICE-netlist-to-Real-Number-Model
pipeline, each built around one circuit and one question.

| | circuit | what it shows |
|---|---|---|
| `demo_1_lpf.sh` | two-pole RC low-pass | the flow works, on real-valued **and** binary input, and emits a UVM-MS environment that runs |
| `demo_2_dcc.sh` | duty-cycle corrector | a good fit is not a valid model — the failure is structural, and only a time-domain check sees it |
| `demo_3_pi.sh` | phase interpolator | measuring what the block actually does when a voltage comparison cannot |

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

Expect roughly one minute for demo 1 and three for demo 2.

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

Demo 1's sixth act additionally needs an Icarus build with **both** UVM and
IEEE 1800-2017 §6.6.7 nettype support, and the Accellera UVM-MS library:

```sh
IVL_PREFIX=~/iverilog-unified-local UVM_MS_LIB=~/uvm_ms_demo/ms ./demo_1_lpf.sh
```

That is a narrower requirement than running the model itself, which is why the
prefix is passed explicitly rather than derived.

## Layout

```
demo_1_lpf.sh  demo_2_dcc.sh  demo_3_pi.sh
harness/
  prbs_vcd.py   PRBS through the LPF model, scored and dumped to VCD
  demo_dcc.py   threshold sweep -> the corrector's actuator characteristic
  dcc_vcd.py    clock in / clock out, SPICE and model on one set of axes
  demo_pi.py    per-code phase measurement across the interpolator
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
