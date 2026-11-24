# spice2rnm demos

Five walkthroughs of **spice2rnm**, Veylon Systems' netlist-to-verified-model
pipeline for mixed-signal verification -- each built around one circuit and
one question.

| | circuit | what it shows |
|---|---|---|
| `demo_1_lpf.sh` | two-pole RC low-pass | the baseline: verified model in under a minute, holding up on binary data, with a running UVM-MS environment |
| `demo_2_dcc.sh` | duty-cycle corrector | level-dependent dynamics: a block that defeats fixed-response modelling, verified by what it does to duty |
| `demo_3_pi.sh` | phase interpolator | a block with no amplitude transfer at all, verified by phase per code |
| `demo_4a_pll_cosim.sh` | phase-locked loop | three characterisation problems in one netlist, composed and checked against the transistors on the design's own co-simulation testbench |
| `demo_4b_pll_nocosim.sh` | the same PLL | the same circuit with no co-simulation anywhere: operating bands read off the deck and the specification instead of probed, and the loop closed around the customer's RTL in pure SystemVerilog |
| `demo_4c_pll_knob_noise.sh` | the same PLL, noise on the knob | demo 4a with the shake moved from the supply to the loop filter's resistors: the filter model carries that noise, each source is replay-checked, and the loop is checked against the transistors again |

The last two are the same circuit from opposite ends. Demo 4a starts from a
co-simulation that already runs and uses it as the reference. Demo 4b starts
where most designs actually are -- an analog netlist, some RTL, a
specification in English, and nothing wiring them together -- and needs no
bridge, no shared libngspice and no testbench spanning the two halves.

The generated artifacts themselves — models, environments, evidence — are
committed under [`showcase/`](showcase/), and the whitepaper under
[`whitepaper/`](whitepaper/).

## Documentation

[`docs/`](docs/) is the whitepaper split into pages you can read one at a
time, each sitting next to the files it describes. Start with
[`docs/the-problem.md`](docs/the-problem.md) for what this is and what one
command gives you, [`docs/cases/`](docs/cases/) for the five circuits and
their results, or [`docs/README.md`](docs/README.md) for the full index. The
same material as one document is
[`whitepaper/spice2rnm-demos.pdf`](whitepaper/spice2rnm-demos.pdf), 35 pages.

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
demo_4a_pll_cosim.sh  demo_4b_pll_nocosim.sh  demo_4c_pll_knob_noise.sh
netlists/
  rc_lpf2.cir    the two-pole filter: demo 1's input
  dcc.cir        the duty-cycle corrector: demo 2
  pi_therm.cir   the phase interpolator: demo 3
  pll_analog.cir the PLL deck demos 4 and 4b run -- ams-cosim's example
                 plus the 20 mV supply-noise card it is run with
  pll_analog_knob.cir  demo 4c's deck: the same PLL, quiet supply,
                 thermal noise (1000x, a stress case) on the loop
                 filter's three resistors
rtl/
  pll/           the PLL's digital half: pfd.sv and divn.sv, the RTL
                 both PLL demos instantiate, and tb_pll.sv, the
                 co-simulation testbench demo 4a runs as its golden
harness/
  prbs_vcd.py    PRBS through the LPF model, scored and dumped to VCD
  demo_dcc.py    threshold sweep -> the corrector's actuator characteristic
  dcc_vcd.py     clock in / clock out, SPICE and model on one set of axes
  demo_pi.py     per-code phase measurement across the interpolator
  wave_bundle.py a run's waveforms for someone else: pictures, zoomable
                 pages, .fst + GTKWave layouts (demo 1 calls it)
  wave_page.py   the zoomable page: data inside, nothing to install
  uvm_wave.py    act 6's UVM-MS run re-run with a recording, drawn with
                 every scoreboard check (about 2 minutes)
  pll_wave.py    demo 4b's PLL loop re-run with a recording, plus its
                 inverters and loop filter, circuit vs model
  uvm_phase_split.py  separates the AC phase checks' built-in offset
                 from the model's own phase error
specs/
  rc_lpf2_spec.md  the filter's specification, in English
  dcc_spec.md      the duty-cycle corrector's -- demo 2 reads it
  pll_spec.md      the PLL's -- demo 4b's third input
```

The harness scripts write under `~/s2r_runs/` and are called by the demos
through `$HARNESS`, so the tree relocates as a unit.

## Waveforms

The quickest look needs nothing installed. Open a page and drag across the
plot to zoom in:

- [PRBS7 at 160 Mb/s through the two-pole filter](https://vrajeshprakhya.github.io/spice2rnm-demos/lpf2/lpf2_prbs.html)
- [the pipeline's own sweep with a chirp on top](https://vrajeshprakhya.github.io/spice2rnm-demos/lpf2/lpf2_chirp.html)
- [the UVM-MS run (demo 1, act 6), every scoreboard check on the waveform](https://vrajeshprakhya.github.io/spice2rnm-demos/lpf2/lpf2_uvm.html)

The first two overlay the circuit (ngspice) and the generated model (xezim)
with their difference underneath. The third draws the verification run:
what the UVM-MS environment drove into the model, what came out, and at
each check what ngspice says the reading should be. Every page carries
every point its run wrote.
The same pages are committed in
[`showcase/lpf2/waveforms/`](showcase/lpf2/waveforms/) beside still
pictures of them, explained in
[the filter's case study](docs/cases/01-two-pole-filter.md#waveforms-worth-opening).

Demo 4b's PLL, where the loop runs on models and RTL alone:

- [the whole loop holding lock](https://vrajeshprakhya.github.io/spice2rnm-demos/pll_nocosim/pll_nocosim_loop.html):
  the control voltage, the oscillator's rate cycle by cycle (with the
  jitter the netlist's supply noise puts on it), the charge pump, the
  phase detector's pulses, the reference against the divided clock
- its blocks, circuit against model:
  [inverter inv1](https://vrajeshprakhya.github.io/spice2rnm-demos/pll_nocosim/pll_nocosim_inv1.html),
  [inverter inv2](https://vrajeshprakhya.github.io/spice2rnm-demos/pll_nocosim/pll_nocosim_inv2.html),
  [the loop filter](https://vrajeshprakhya.github.io/spice2rnm-demos/pll_nocosim/pll_nocosim_lpfilt.html)

These are committed in
[`showcase/pll_nocosim/waveforms/`](showcase/pll_nocosim/waveforms/) and
rebuilt on every refresh by `harness/pll_wave.py`.

Demo 1 ends by building all of this, plus waveform files (`.fst`) and
GTKWave layouts that open them already drawn as curves, in a folder you can
hand to someone, `~/s2r_runs/lpf2_wave/`:

```sh
cd ~/s2r_runs/lpf2_wave && gtkwave lpf2_prbs.fst lpf2_prbs.gtkw
```

The PRBS `.fst` is small enough to sit in the showcase; the chirp's (7 MB)
is on the [Releases page](https://github.com/vrajeshprakhya/spice2rnm-demos/releases)
with the rest of the folder. The other demos do not build such a folder
yet.

The raw dumps are still written, for debugging:

```sh
gtkwave ~/s2r_runs/lpf2_vcd/tb_prbs.vcd
gtkwave ~/s2r_runs/dcc2_vcd/tb_dcc.vcd
```

In those, reals render as decimal numbers until you tell GTKWave otherwise.
For each of `spice_ref`, `out_val` and `err`: right-click → Data Format →
Analog → Interpolated.
