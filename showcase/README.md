# What spice2rnm actually generates

*spice2rnm is a Veylon Systems product.*

This directory holds the **unedited output** of the demo runs: the
SystemVerilog real-number models, the complete UVM-MS verification
environments, and the evidence files, exactly as the tool wrote them. One
command produced each case:

```sh
spice2rnm <netlist> --input-node <in> --output-node <out> --emit-uvm-ms
```

Nothing generated here is hand-edited. `refresh.sh` regenerates the whole
directory and stamps `STAMP` with the tool version and the run summary —
if these files and the tool ever disagree, the refresh is the fix, not an
edit.

One directory is deliberately *not* generated: [`house_lib/`](house_lib/)
is a small hand-written model library standing in for a customer's
existing one, so that `lpf2_house/` can demonstrate joining it rather than
merely describing what that would look like. Its own README says so.

| Case | Circuit | What it shows |
|------|---------|---------------|
| [`lpf2/`](lpf2/) | two-pole RC filter | the baseline: DC + AC environment |
| [`dcc2/`](dcc2/) | duty-cycle corrector | level-dependent dynamics; duty checked instead of AC |
| [`pi/`](pi/) | phase interpolator | phase-per-code environment; no DC or AC at all |
| [`lpf2_house/`](lpf2_house/) | the filter again | the same circuit generated against an existing model library — see below |

## Where to look first

**The model headers.** Open `dcc2/dcc_rnm.sv` and read the first fifteen
lines. Every structural choice in the model carries the *measurement* that
justified it — the 33-point measured rate schedule, the 94.66 ps rise/fall
skew and where it came from. Hand-written models do not ship with their own
evidence; these cannot ship without it.

**The scoreboards.** Open `dcc2/dcc_ms_scoreboard.svh` or
`lpf2/rc_lpf2_ms_scoreboard.svh`. The header states the rule the whole
product is built on: golden values are SPICE measurements of the circuit,
never the fitted equations — a model checked against its own equations
passes unconditionally and means nothing.

**The duty golden table.** In `dcc2/dcc_ms_pkg.sv`, the `duty_freq` /
`duty_in` / `duty_gold` / `duty_vth` functions hold per-point ngspice
measurements of what the circuit does to duty — including the threshold
each point is sliced at, frozen from ngspice's own trace so the model
cannot influence its own pass.

**A different environment when the block needs one.** `pi/` has no DC and
no AC section, because neither describes edge placement. Its scoreboard
holds one measured phase golden per thermometer code, checked to a tenth
of an LSB.

**The wreal boundary.** Each case also carries a `*_wreal.sv` wrapper —
the same core model behind `wreal` ports, for flows standardised on wreal
nets. Ten lines of discipline conversion around an untouched core:
adopting the model never means adopting a net discipline.

**The evidence.** Each case's `result.json` and `pipeline.txt` are the
tool's own record of the run: the fit, the equivalence verdict, and every
warning it raised on the way — including the measurements behind choices
like omitting the AC section.

## If you already have an RNM library

`lpf2/` and `dcc2/` and `pi/` show the **default** boundary: each emits its
own types package (`*_ms_types_pkg.sv`) declaring a nettype named after the
block. That is right for a team starting fresh and wrong for a team that
already has a library — generated files importing their own
freshly-invented nettype do not join yours, they sit beside it.

So there is a fourth case. [`house_lib/`](house_lib/) is a small
hand-written library standing in for yours: a package declaring
`nettype real ng_anet`, and two models using it.
[`lpf2_house/`](lpf2_house/) is **the same circuit as `lpf2/`**, generated
against it with `--style-from`. Diff the two directories:

```sh
diff -r lpf2 lpf2_house
```

| | `lpf2/` | `lpf2_house/` |
|---|---|---|
| types package | `rc_lpf2_ms_types_pkg.sv` emitted | **not emitted** — `house_lib` already declares the net |
| nets | `rc_lpf2_wire` | `ng_anet` |
| imports | `rc_lpf2_ms_types_pkg::*` | `ng_ams_pkg::*` |
| run script | compiles the generated package | compiles `../house_lib/ng_ams_pkg.sv` (`HOUSE_NET_SRC` override) |

**The model file is byte-identical between the two.** So is the
scoreboard. Conformance changes the boundary and nothing else — and
`lpf2_house/run_rc_lpf2_ms.sh` runs from where it sits, against the
library next door, with the same result the default environment gives:
51 DC and 19 AC checks, 0 failed.

A library that uses `wreal` ports rather than a nettype gets the wreal
wrapper emitted unasked instead; measured separately, a library resolving
its net by averaging rather than summing conforms and passes the same way.

Reading a library's conventions is a judgement call, so it is read and
then verified: which of several declared nettypes is the living standard
is often stated only in a comment, and whatever the tool concludes is
re-checked against the file that supposedly shows it before anything uses
it. A claim the file does not support is refused, and the run says so.

## Running the environments yourself

Each case's `run_*.sh` compiles and runs its environment. The scripts
default to `$HOME`-relative tool paths and take overrides from the
environment:

```sh
cd dcc2
IVL_PREFIX=/path/to/icarus-uvm UVM_MS_LIB=/path/to/uvm-ms bash run_dcc_ms.sh
```

They need an Icarus-compatible simulator with UVM support and the
Accellera UVM-MS library. Expected result, from the stamped run:

```
lpf2         dc checks=51 failed=0 | ac checks=19 failed=0
dcc2         dc checks=51 failed=0 | duty checks=15 failed=0 (worst 0.314 pp of 0.500)
pi           phase checks=9 failed=0 (worst 3.26 ps of 6.25 ps)
lpf2_house   dc checks=51 failed=0 | ac checks=19 failed=0   (on the house net)
```

## What is deliberately not here

The run directories also contain characterisation scratch, compiled
simulator objects and DPI shims. Those are build products, not
deliverables, and `refresh.sh` filters them out — what you see here is
what a user would keep.
