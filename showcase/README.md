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

## Every file, and what is in it

The four cases share one file naming scheme, so a file does the same job
in each. `lpf2/` in full:

```
lpf2/
  rc_lpf2_rnm.sv              THE MODEL. Plain `real` ports, the fitted
                              structure, and in its header the measurements
                              that chose that structure
  rc_lpf2_rnm_wreal.sv        the same model behind wreal ports, for flows
                              standardised on wreal nets
  rc_lpf2_ms_types_pkg.sv     the generated user-defined nettype the
                              environment's analog nets travel on
  rc_lpf2_dms.sv              net <-> variable wrapper: interconnect ports
                              outside, the model's real ports inside
  rc_lpf2_bridge.sv           MS bridge: the concrete proxy the class-based
                              testbench drives the analog side through
  rc_lpf2_bridge_core.sv      what actually drives and senses the DUT pins,
                              including the settling and AC measurement
  rc_lpf2_proxy_pkg.sv        the abstract proxy: the API between agent and
                              bridge, so either side can be swapped
  rc_lpf2_ms_pkg.sv           the agent -- item, driver, monitor, sequences
                              -- AND THE GOLDEN TABLES measured from ngspice
  rc_lpf2_ms_scoreboard.svh   the checks, and the tolerances, with the
                              reasoning for each tolerance in comments
  rc_lpf2_ms_tb.svh           the environment: agent + scoreboard wiring
  rc_lpf2_ms_test.svh         the UVM test that runs the sequences
  top_rc_lpf2_ms.sv           top level: nets, DUT, bridge, test
  run_rc_lpf2_ms.sh           compiles and runs the whole thing
  result.json                 the run's own record: fit, verdict, warnings
```

### Where each example actually lives

| Looking for | Open |
|---|---|
| a generated model, plain `real` ports | [`lpf2/rc_lpf2_rnm.sv`](lpf2/rc_lpf2_rnm.sv) |
| a model with **wreal** ports | [`lpf2/rc_lpf2_rnm_wreal.sv`](lpf2/rc_lpf2_rnm_wreal.sv) |
| a model with **UDN** ports, on a library's own nettype | [`lpf2_house/rc_lpf2_rnm_ng_anet.sv`](lpf2_house/rc_lpf2_rnm_ng_anet.sv) |
| a **UDN declaration** the tool generated | [`lpf2/rc_lpf2_ms_types_pkg.sv`](lpf2/rc_lpf2_ms_types_pkg.sv) |
| a **UDN declaration** a customer already had | [`house_lib/ng_ams_pkg.sv`](house_lib/ng_ams_pkg.sv) |
| an environment on **its own** nettype | [`lpf2/top_rc_lpf2_ms.sv`](lpf2/top_rc_lpf2_ms.sv) |
| an environment on **a library's** nettype | [`lpf2_house/top_rc_lpf2_ms.sv`](lpf2_house/top_rc_lpf2_ms.sv) |
| `interconnect` ports (IEEE 1800-2017 §6.6.8) | [`lpf2/rc_lpf2_dms.sv`](lpf2/rc_lpf2_dms.sv) |
| goldens that are **SPICE measurements** | [`lpf2/rc_lpf2_ms_pkg.sv`](lpf2/rc_lpf2_ms_pkg.sv) (`gold_x`/`gold_y`, `ac_freq`/`ac_mag_db`) |
| a model whose **dynamics move with level** | [`dcc2/dcc_rnm.sv`](dcc2/dcc_rnm.sv) — 33-point rate schedule, measured rise/fall skew |
| **duty** goldens, where AC cannot apply | [`dcc2/dcc_ms_pkg.sv`](dcc2/dcc_ms_pkg.sv) (`duty_freq`/`duty_in`/`duty_gold`/`duty_vth`) |
| why an environment has **no AC section** | [`dcc2/pipeline.txt`](dcc2/pipeline.txt) — the run says it in its own words |
| a **delay-line** model (no transfer function at all) | [`pi/pi_therm_rnm.sv`](pi/pi_therm_rnm.sv) |
| **phase-per-code** goldens | [`pi/pi_therm_ms_pkg.sv`](pi/pi_therm_ms_pkg.sv) |
| a **digital code port** crossing an analog boundary | [`pi/pi_therm_rnm_wreal.sv`](pi/pi_therm_rnm_wreal.sv) — `input int code` stays `int` |
| what a **conformed** run script compiles | [`lpf2_house/run_rc_lpf2_ms.sh`](lpf2_house/run_rc_lpf2_ms.sh) — the house package, not a generated one |

`dcc2/` and `pi/` differ from the list above only where their block does:
`dcc2/` has no AC section and adds `pipeline.txt`; `pi/` has neither a DC
nor an AC section and no bridge pair, because its environment measures
edges directly. `lpf2_house/` has no `*_ms_types_pkg.sv` — that is the
point of it — and adds the `ng_anet` boundary instead of a wreal one.

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
| model ports | plain `real` | `ng_anet` — and the environment instantiates that module, so what is verified is what ships |

**The model file is byte-identical between the two.** So is the
scoreboard. The computing core never changes; `lpf2_house/` simply adds
`rc_lpf2_rnm_ng_anet.sv`, the boundary presenting the house net, which is
the module its testbench drives. Conformance changes the boundary and
nothing else — and
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
