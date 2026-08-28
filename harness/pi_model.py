#!/usr/bin/env python3
"""Turn the measured phase-vs-code table into an RNM, then SIMULATE it.

Reads the CSV demo_pi.py just wrote rather than re-sweeping: act 4 does the
measurement, this does the model, and using the same numbers is the point --
a table measured twice could differ, and then the comparison below would be
measuring that instead of the model.

The check that matters is the last one. Comparing a model against the table
it was built from proves nothing; this drives the generated SystemVerilog
with a clock, finds the output's falling edge, and asks whether it landed
where the circuit put it.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "spice2rnm"))
from spice2rnm.code_phase import generate_code_delay_rnm  # noqa: E402

XEZIM = Path.home() / "xezim/target/release/xezim"
OUT = Path.home() / "s2r_runs/demo_pi"
CSV = OUT / "phase_vs_code.csv"
MODEL_DIR = OUT / "model"
PERIOD = 2e-9
IN_FALL = PERIOD / 2.0
N_CYC = 14

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

MODEL_DIR.mkdir(parents=True, exist_ok=True)
sv = generate_code_delay_rnm(rows, "pi_rnm")
sv_path = MODEL_DIR / "pi_rnm.sv"
sv_path.write_text(sv)

print("  generated %s  (%d lines)" % (sv_path, len(sv.splitlines())))
for line in sv.splitlines():
    t = line.strip()
    if t.startswith("localparam int  NC") or t.startswith("localparam int  NH") \
            or t.startswith("localparam real TSTEP"):
        print("    %s" % t)
print()
print("  the model is a delay line, one entry per code:")
for line in sv.splitlines():
    if line.startswith("//   ") and ("code" in line or "|" in line
                                     or line.strip("/ ").split()[:1]):
        print("  %s" % line)
    if line.startswith("module"):
        break
print()

base = min(r[1] for r in rows)


def model_phase(slot):
    d = MODEL_DIR / ("run%d" % slot)
    d.mkdir(exist_ok=True)
    tb = ["`timescale 1fs/1fs", "module tb;",
          "  real in_val, out_val;", "  int code;", "  integer fh;",
          "  pi_rnm dut(.in_val(in_val), .code(code), .out_val(out_val));",
          "  initial begin", '    fh = $fopen("%s/out.txt", "w");' % d,
          "    forever begin", "      #(1000);",
          '      $fwrite(fh, "%.9e %.9g\\n", $realtime/1.0e15, out_val);',
          "    end", "  end",
          "  initial begin", "    code = %d;" % slot, "    in_val = 1.0;"]
    t = 0.0
    for k in range(N_CYC):
        for tt, v in ((k * PERIOD + IN_FALL, 0.0), ((k + 1) * PERIOD, 1.0)):
            if tt - t > 0:
                tb.append("    #(%.6f);" % ((tt - t) * 1e15))
            tb.append("    in_val = %.6f;" % v)
            t = tt
    tb += ["    #(1000000);", "    $fclose(fh);", "    $finish;", "  end",
           "endmodule"]
    (d / "tb.sv").write_text("\n".join(tb) + "\n")
    subprocess.run([str(XEZIM), str(sv_path), str(d / "tb.sv")],
                   capture_output=True, text=True, timeout=600)
    if not (d / "out.txt").exists():
        return None
    pairs = []
    for line in (d / "out.txt").read_text().split("\n"):
        f = line.split()
        if len(f) >= 2:
            try:
                pairs.append((float(f[0]), float(f[1])))
            except ValueError:
                pass
    pairs = [p for p in pairs if p[0] >= 4 * PERIOD]
    if len(pairs) < 10:
        return None
    vs = [v for _, v in pairs]
    vth = 0.5 * (max(vs) + min(vs))
    cr = [t0 + (t1 - t0) * (vth - v0) / (v1 - v0)
          for (t0, v0), (t1, v1) in zip(pairs, pairs[1:])
          if (v0 < vth) != (v1 < vth) and v1 != v0 and v1 < v0]
    if len(cr) < 3:
        return None
    return sum(c % PERIOD for c in cr) / len(cr)


print("  simulating the generated model, one run per code:")
print()
print("    code   circuit(ps)   model(ps)   error(ps)")
print("    " + "-" * 46)
worst = 0.0
missing = 0
for slot, (code, ph, sw, ji) in enumerate(rows):
    want = IN_FALL + (ph - base)
    got = model_phase(slot)
    if got is None:
        print("    %4d   %11.1f      (no edges)" % (code, want * 1e12))
        missing += 1
        continue
    err = (got - want) * 1e12
    worst = max(worst, abs(err))
    print("    %4d   %11.1f   %9.1f   %+9.2f"
          % (code, want * 1e12, got * 1e12, err))

lsb = abs(rows[-1][1] - rows[0][1]) / max(len(rows) - 1, 1) * 1e12
print()
if missing:
    print("    %d code(s) produced no edge" % missing)
print("    worst error %.2f ps against a %.1f ps LSB  (%.1f%% of an LSB)"
      % (worst, lsb, 100.0 * worst / lsb if lsb else float("nan")))
