#!/usr/bin/env python3
"""Generate the PI's UVM-MS phase testbench and run it.

Reads the same phase table act 4 measured and act 5 turned into a model,
so all three acts are talking about one measurement rather than three.

What this checks that act 5 does not: act 5 drives the model from a plain
testbench and compares edge positions in Python. This builds the UVM-MS
environment the other two demos show -- user-defined nettype, interconnect
ports, uvm_ms library -- and lets its scoreboard make the call, against
goldens that are ngspice measurements rather than points read back from
the model's own delay table.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path.home() / "spice2rnm"))
from spice2rnm.code_phase import generate_code_delay_rnm  # noqa: E402
from spice2rnm.uvm_ms_phase_codegen import (  # noqa: E402
    generate_uvm_ms_phase_tb,
)

OUT = Path.home() / "s2r_runs/demo_pi"
CSV = OUT / "phase_vs_code.csv"
TB = OUT / "uvm_ms"
PERIOD = 2e-9

if not CSV.exists():
    print("  no phase table at %s -- run the sweep first" % CSV)
    raise SystemExit(1)

rows = []
for line in CSV.read_text().splitlines()[1:]:
    f = line.split(",")
    if len(f) >= 4:
        rows.append((int(f[0]), float(f[1]) * 1e-12, float(f[3]), float(f[2])))
if len(rows) < 2:
    print("  phase table has %d usable rows" % len(rows))
    raise SystemExit(1)

TB.mkdir(parents=True, exist_ok=True)
(TB / "pi_rnm.sv").write_text(generate_code_delay_rnm(rows, "pi_rnm"))

notes = []
files = generate_uvm_ms_phase_tb(
    rows, period=PERIOD, rnm_module="pi_rnm", rnm_file="pi_rnm.sv",
    base="pi", v_lo=0.0, v_hi=1.0, notes=notes)
for name, text in files.items():
    (TB / name).write_text(text)
    if name.endswith(".sh"):
        (TB / name).chmod(0o755)

print("  %d files in %s" % (len(files) + 1, TB))
for name in sorted(files):
    print("      %s" % name)
print()
for n in notes:
    lines = textwrap.wrap(n, 66)
    for i, chunk in enumerate(lines):
        print("    %s%s" % ("- " if i == 0 else "  ", chunk))
print()

r = subprocess.run(["bash", str(TB / "run_pi_ms.sh")],
                   capture_output=True, text=True, timeout=900, cwd=str(TB))
out = (r.stdout or "") + (r.stderr or "")
keep = ("SB_SUMMARY", "PHASE_CHECK", "UVM_ERROR :", "UVM_FATAL :",
        "COMPILE FAILED", "=== ")
seen = set()
for line in out.splitlines():
    if any(k in line for k in keep) and line not in seen:
        seen.add(line)
        print("    %s" % line)
