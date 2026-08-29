#!/usr/bin/env python3
"""Bit-rate sweep, corrected.

The first sweep held BIT COUNT constant, so the simulated window shrank as
1/rate: 12.8 us at 5 Mb/s but only 100 ns at 640 Mb/s. The two sides also
start from different states -- the RNM initialises at its DC_BIAS while
ngspice solves an operating point at the first bit's level -- and that
startup transient decays with the filter's own tau (41.6 ns). At low rates
it is long dead before the comparison window opens; at high rates it IS the
window. So the apparent "breakdown" was settling from a mismatched initial
condition, not a failure to track data. Refining the model timestep 10x
changed nothing, which is what ruled the integration step out.

This version holds the simulated DURATION constant (bit count scales with
rate) and opens the comparison after 10 tau, so startup is a fixed, small
fraction at every rate and what remains is tracking error.
"""
import subprocess, math, re
from pathlib import Path

HOME = Path.home()
NGSPICE = HOME / "ngspice-install/bin/ngspice"
XEZIM = HOME / "xezim/target/release/xezim"
NETLIST = HOME / "spice2rnm/work/rc_lpf2.cir"
RNM = HOME / "s2r_runs/lpf2/rc_lpf2_rnm.sv"
OUT = HOME / "s2r_runs/lpf2_sweep2"
OUT.mkdir(parents=True, exist_ok=True)

DURATION = 4.0e-6
V_LO, V_HI = 0.1, 1.7
RATES = [5e6, 10e6, 20e6, 40e6, 80e6, 160e6, 320e6]

src = RNM.read_text()
DT = float(re.search(r"localparam real DT_SECONDS\s*=\s*([0-9.eE+-]+)", src).group(1))
POLE0 = float(re.search(r"poles \(Hz\): \[([0-9.eE+-]+)", src).group(1))
TAU = 1.0 / (2 * math.pi * POLE0)
SETTLE = 10 * TAU
print(f"tau = {TAU*1e9:.1f} ns   comparison opens at 10*tau = {SETTLE*1e9:.0f} ns")
print(f"fixed simulated duration = {DURATION*1e6:.1f} us")
print()


def prbs15(n, seed=0x4A31):
    s, out = seed & 0x7FFF, []
    for _ in range(n):
        b = ((s >> 14) ^ (s >> 13)) & 1
        s = ((s << 1) | b) & 0x7FFF
        out.append(b)
    return out


def sv_real(x, sig=9):
    s = f"{float(x):.{sig}g}"
    return s if any(c in s for c in ".eE") else s + ".0"


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


def read_cols(p):
    out = []
    for line in Path(p).read_text().split("\n"):
        f = line.split()
        if len(f) >= 2:
            try: out.append((float(f[0]), float(f[1])))
            except ValueError: pass
    return out


rows = []
for rate in RATES:
    ui = 1.0 / rate
    n_bits = int(DURATION * rate)
    trise = min(2e-9, ui / 10.0)
    t_end = n_bits * ui
    tag = f"{rate/1e6:.0f}M"
    d = OUT / tag
    d.mkdir(exist_ok=True)
    bits = prbs15(n_bits)

    pts = [(0.0, V_HI if bits[0] else V_LO)]
    for i, b in enumerate(bits):
        v = V_HI if b else V_LO
        t0 = i * ui
        if i > 0 and pts[-1][1] != v:
            pts.append((t0, pts[-1][1])); pts.append((t0 + trise, v))
        else:
            pts.append((t0 + trise, v))
        pts.append(((i + 1) * ui, v))
    clean = []
    for t, v in pts:
        if clean and t <= clean[-1][0]: t = clean[-1][0] + 1e-15
        clean.append((t, v))
    pts = clean

    pwl = " ".join(f"{t:.12e} {v:.9g}" for t, v in pts)
    deck = [l for l in NETLIST.read_text().splitlines()
            if not l.strip().upper().startswith("VIN ")
            and not l.strip().lower().startswith(".end")]
    step = min(ui / 50.0, 2e-10)
    deck += [f"VIN vin 0 PWL({pwl})", ".control",
             f"tran {step:.12e} {t_end:.12e} 0 {step:.12e}",
             f"wrdata {d}/spice.txt v(vout)", ".endc", ".end"]
    (d / "prbs.cir").write_text("\n".join(deck) + "\n")
    subprocess.run([str(NGSPICE), "-b", str(d / "prbs.cir")],
                   capture_output=True, text=True, timeout=1800)
    if not (d / "spice.txt").exists():
        print(f"  {tag}: ngspice failed"); continue
    spice = read_cols(d / "spice.txt")

    sample = min(ui / 20.0, 2e-10)
    tb = ["`timescale 1fs/1fs", "module tb;", "  real in_val, out_val;",
          "  integer logfile;",
          "  rc_lpf2_rnm dut(.in_val(in_val), .out_val(out_val));",
          "  initial begin", f'    logfile = $fopen("{d}/model.txt", "w");',
          "    forever begin", f"      #({sample*1e15:.6f});",
          '      $fwrite(logfile, "%.9e %.9g\\n", $realtime/1.0e15, out_val);',
          "    end", "  end", "  initial begin"]
    prev = 0.0
    for t, v in pts:
        tfs = t * 1e15
        if tfs - prev > 0: tb.append(f"    #({tfs-prev:.6f});")
        tb.append(f"    in_val = {sv_real(v)};")
        prev = tfs
    tb += ["    $fclose(logfile);", "    $finish;", "  end", "endmodule"]
    (d / "tb.sv").write_text("\n".join(tb) + "\n")
    subprocess.run([str(XEZIM), str(RNM), str(d / "tb.sv")],
                   capture_output=True, text=True, timeout=3600)
    if not (d / "model.txt").exists():
        print(f"  {tag}: xezim failed"); continue
    model = read_cols(d / "model.txt")
    if not spice or not model:
        print(f"  {tag}: empty"); continue

    t0c = SETTLE
    t1c = min(spice[-1][0], model[-1][0], t_end)
    grid = [t0c + (t1c - t0c) * i / 3999 for i in range(4000)]
    sv = [interp(model, t) for t in grid]
    sp = [interp(spice, t) for t in grid]
    df = [a - b for a, b in zip(sv, sp)]
    exc = max(sp) - min(sp)
    rms = math.sqrt(sum(x*x for x in df) / len(df))
    mx = max(abs(x) for x in df)
    bias = sum(df) / len(df)
    rows.append((rate, n_bits, ui / DT, exc, rms / exc, mx / exc, bias / exc))
    print(f"  {tag:>5} done  ({n_bits} bits)", flush=True)

print()
print("  rate   bits   steps/UI   ref exc     rms norm   max norm   mean err   verdict")
print("  " + "-" * 78)
for rate, nb, spui, exc, rn, mn, bn in rows:
    print(f"  {rate/1e6:4.0f}M  {nb:5d}   {spui:7.1f}   {exc:8.5f}V   {rn:8.5f}   "
          f"{mn:8.5f}   {bn:+8.5f}   {'PASS' if rn <= 0.15 else 'FAIL'}")
