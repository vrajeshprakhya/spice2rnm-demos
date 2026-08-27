#!/usr/bin/env python3
"""PRBS through the RC-LPF RNM, with a WAVEFORM DUMP you can actually look at.

The earlier harnesses wrote text traces only, so every result was a number
with no way to see it. This mirrors what the pipeline's own equivalence
testbench does: replay the ngspice result into the testbench as `spice_ref`,
compute `err` live, and dump the lot to VCD -- so SPICE, the model and the
residual sit in one GTKWave view, time-aligned.

Short by design: 128 bits at 160 Mb/s is 800 ns, which is a window you can
actually read on screen. The point is to SEE the ISI -- and to score it the
same way prbs_sweep2.py and the pipeline's own equivalence check do, so the
number quoted beside the picture comes from this run and is comparable to
the chirp figure rather than being a third incompatible measurement.
"""
import subprocess, math, re
from pathlib import Path

HOME = Path.home()
NGSPICE = HOME / "ngspice-install/bin/ngspice"
XEZIM = HOME / "xezim/target/release/xezim"
NETLIST = HOME / "spice2rnm/work/rc_lpf2.cir"
RNM = HOME / "s2r_runs/lpf2/rc_lpf2_rnm.sv"
OUT = HOME / "s2r_runs/lpf2_vcd"
OUT.mkdir(parents=True, exist_ok=True)

RATE = 160e6
N_BITS = 128
V_LO, V_HI = 0.1, 1.7
UI = 1.0 / RATE
TRISE = min(2e-9, UI / 10.0)
T_END = N_BITS * UI

src = RNM.read_text()
DT = float(re.search(r"localparam real DT_SECONDS\s*=\s*([0-9.eE+-]+)", src).group(1))
POLE0 = float(re.search(r"poles \(Hz\): \[([0-9.eE+-]+)", src).group(1))
TAU = 1 / (2 * math.pi * POLE0)
print(f"{RATE/1e6:.0f} Mb/s, UI={UI*1e9:.2f} ns, {N_BITS} bits -> {T_END*1e9:.0f} ns")
print(f"filter tau = {TAU*1e9:.1f} ns  ({TAU/UI:.1f} UI) -- so ISI should be plainly visible")

# Score from 10 tau, the same settle prbs_sweep2.py uses. The model opens from
# zero state while ngspice opens from its DC operating point, so the first
# decade of tau compares two different initial conditions rather than two
# responses -- scoring through it reported 0.0972 where the settled figure is
# 0.0097, and the difference is entirely that transient.
SETTLE = 10 * TAU
LOG_DT = min(UI / 20.0, 2e-10)


def interp(tr, t):
    if t <= tr[0][0]: return tr[0][1]
    if t >= tr[-1][0]: return tr[-1][1]
    lo, hi = 0, len(tr) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if tr[mid][0] <= t: lo = mid
        else: hi = mid
    (t0, v0), (t1, v1) = tr[lo], tr[hi]
    return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
print()


def prbs7(n, seed=0x41):
    s, out = seed & 0x7F, []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1
        s = ((s << 1) | b) & 0x7F
        out.append(b)
    return out


def sv_real(x, sig=9):
    s = f"{float(x):.{sig}g}"
    return s if any(c in s for c in ".eE") else s + ".0"


bits = prbs7(N_BITS)
pts = [(0.0, V_HI if bits[0] else V_LO)]
for i, b in enumerate(bits):
    v = V_HI if b else V_LO
    t0 = i * UI
    if i > 0 and pts[-1][1] != v:
        pts.append((t0, pts[-1][1])); pts.append((t0 + TRISE, v))
    else:
        pts.append((t0 + TRISE, v))
    pts.append(((i + 1) * UI, v))
clean = []
for t, v in pts:
    if clean and t <= clean[-1][0]: t = clean[-1][0] + 1e-15
    clean.append((t, v))
pts = clean

# --- ngspice reference ----------------------------------------------------
pwl = " ".join(f"{t:.12e} {v:.9g}" for t, v in pts)
deck = [l for l in NETLIST.read_text().splitlines()
        if not l.strip().upper().startswith("VIN ")
        and not l.strip().lower().startswith(".end")]
step = UI / 100.0
deck += [f"VIN vin 0 PWL({pwl})", ".control",
         f"tran {step:.12e} {T_END:.12e} 0 {step:.12e}",
         f"wrdata {OUT}/spice.txt v(vout)", ".endc", ".end"]
(OUT / "prbs.cir").write_text("\n".join(deck) + "\n")
print("running ngspice ...", flush=True)
subprocess.run([str(NGSPICE), "-b", str(OUT / "prbs.cir")],
               capture_output=True, text=True, timeout=900)
spice = []
for line in (OUT / "spice.txt").read_text().split("\n"):
    f = line.split()
    if len(f) >= 2:
        try: spice.append((float(f[0]), float(f[1])))
        except ValueError: pass
print(f"  {len(spice)} reference points")

# --- testbench: stimulus, spice replay, live error, VCD -------------------
VCD = OUT / "tb_prbs.vcd"
tb = ["`timescale 1fs/1fs", "module tb;",
      "  real in_val, out_val;",
      "  real spice_ref, err;",
      "  rc_lpf2_rnm dut(.in_val(in_val), .out_val(out_val));",
      "",
      "  // the residual, computed live so it is a trace in its own right",
      "  always @(out_val, spice_ref) err = out_val - spice_ref;",
      "",
      "  // Logged CONCURRENTLY. Writing the trace after the stimulus block",
      "  // finishes captures an empty window -- a bug this harness has had,",
      "  // and one that reads as a plausible rms rather than as a failure.",
      "  integer logfile;",
      "  initial begin",
      f'    logfile = $fopen("{OUT}/model.txt", "w");',
      "    forever begin",
      f"      #({LOG_DT*1e15:.6f});",
      '      $fwrite(logfile, "%.9e %.9g\\n", $realtime/1.0e15, out_val);',
      "    end",
      "  end",
      "",
      "  initial begin",
      f'    $dumpfile("{VCD}");',
      "    // depth 0 -- pulls the RNM's RK4 internals in too, which is what",
      "    // you want when a divergence needs explaining rather than scoring",
      "    $dumpvars(0, tb);",
      "  end",
      "",
      "  // ngspice result, replayed on its own timeline",
      "  initial begin"]
prev = 0.0
for t, v in spice:
    tfs = t * 1e15
    if tfs - prev > 0: tb.append(f"    #({tfs-prev:.6f});")
    tb.append(f"    spice_ref = {sv_real(v)};")
    prev = tfs
tb += ["  end", "", "  // the stimulus", "  initial begin"]
prev = 0.0
for t, v in pts:
    tfs = t * 1e15
    if tfs - prev > 0: tb.append(f"    #({tfs-prev:.6f});")
    tb.append(f"    in_val = {sv_real(v)};")
    prev = tfs
tb += [f"    #({2*UI*1e15:.6f});", "    $fclose(logfile);",
       "    $finish;", "  end", "endmodule"]
(OUT / "tb_prbs.sv").write_text("\n".join(tb) + "\n")

print("running xezim ...", flush=True)
r = subprocess.run([str(XEZIM), str(RNM), str(OUT / "tb_prbs.sv")],
                   capture_output=True, text=True, timeout=1800)
if not VCD.exists():
    print("no vcd:\n", r.stdout[-2000:], r.stderr[-2000:]); raise SystemExit(1)

size = VCD.stat().st_size
print(f"  vcd: {size/1e6:.1f} MB")

model = []
mp = OUT / "model.txt"
if mp.exists():
    for line in mp.read_text().split("\n"):
        f = line.split()
        if len(f) >= 2:
            try: model.append((float(f[0]), float(f[1])))
            except ValueError: pass

if not model:
    print("  score unavailable: the model trace is empty")
else:
    t0c = SETTLE
    t1c = min(spice[-1][0], model[-1][0], T_END)
    grid = [t0c + (t1c - t0c) * i / 3999 for i in range(4000)]
    sv = [interp(model, t) for t in grid]
    sp = [interp(spice, t) for t in grid]
    df = [a - b for a, b in zip(sv, sp)]
    exc = max(sp) - min(sp)
    rms = math.sqrt(sum(x * x for x in df) / len(df)) / exc
    mx = max(abs(x) for x in df) / exc
    print(f"  rms {rms:.4f} normalized   max {mx:.4f}   "
          f"(threshold 0.15)   {'PASS' if rms <= 0.15 else 'FAIL'}")
    print(f"    {len(grid)} points over {t0c*1e9:.0f}..{t1c*1e9:.0f} ns "
          f"(10 tau settle), reference excursion {exc:.4f} V")
print()
print("  open it with:")
print(f"    gtkwave {VCD}")
print()
print("  then, for each of spice_ref / out_val / err:")
print("    right-click -> Data Format -> Analog -> Interpolated")
print("  (reals render as numbers until you do; err on its own with")
print("   autoscale is where the residual actually becomes visible)")
