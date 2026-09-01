# What spice2rnm actually generates

This directory holds the **unedited output** of the three demo runs: the
SystemVerilog real-number models, the complete UVM-MS verification
environments, and the evidence files, exactly as the tool wrote them. One
command produced each case:

```sh
spice2rnm <netlist> --input-node <in> --output-node <out> --emit-uvm-ms
```

Nothing here is hand-written and nothing is hand-edited. `refresh.sh`
regenerates the whole directory from the demos and stamps `STAMP` with the
tool version and the run summary — if these files and the tool ever
disagree, the refresh is the fix, not an edit.

| Case | Circuit | What it shows |
|------|---------|---------------|
| [`lpf2/`](lpf2/) | two-pole RC filter | the baseline: DC + AC environment |
| [`dcc2/`](dcc2/) | duty-cycle corrector | level-dependent dynamics; duty checked instead of AC |
| [`pi/`](pi/) | phase interpolator | phase-per-code environment; no DC or AC at all |

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

**The evidence.** Each case's `result.json` and `pipeline.txt` are the
tool's own record of the run: the fit, the equivalence verdict, and every
warning it raised on the way — including the measurements behind choices
like omitting the AC section.

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
lpf2   dc checks=51 failed=0 | ac checks=19 failed=0
dcc2   dc checks=51 failed=0 | duty checks=15 failed=0 (worst 0.314 pp of 0.500)
pi     phase checks=9 failed=0 (worst 3.26 ps of 6.25 ps)
```

## What is deliberately not here

The run directories also contain characterisation scratch, compiled
simulator objects and DPI shims. Those are build products, not
deliverables, and `refresh.sh` filters them out — what you see here is
what a user would keep.
