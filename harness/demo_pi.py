#!/usr/bin/env python3
"""PI demo: thermometer-coded phase interpolation, phase vs code.

Code k enables k unit cells on phase I and 8-k on phase Q. Every code moves
exactly one unit of current from one phase to the other, so the summed
node's crossing should advance by a near-constant step -- linearity coming
from cell matching rather than from any device staying in a linear region.

Reports the same figures a PI is specified by: phase vs code, DNL, INL.
"""
import subprocess, math, statistics
from pathlib import Path

HOME = Path.home()
NGSPICE = HOME / "ngspice-install/bin/ngspice"
NETLIST = HOME / "spice2rnm/work/pi_therm.cir"
OUT = HOME / "s2r_runs/demo_pi"
OUT.mkdir(parents=True, exist_ok=True)

PERIOD = 2e-9
Q_SHIFT = 500e-12
N_CELLS = 8
N_CYC = 12
T_END = N_CYC * PERIOD
VB_ON = 0.68


def crossings(tr, vth):
    out = []
    for (t0, v0), (t1, v1) in zip(tr, tr[1:]):
        if (v0 < vth) != (v1 < vth) and v1 != v0:
            out.append((t0 + (t1 - t0) * (vth - v0) / (v1 - v0),
                        "rise" if v1 > v0 else "fall"))
    return out


def read(p):
    o = []
    for line in Path(p).read_text().split("\n"):
        f = line.split()
        if len(f) >= 2:
            try: o.append((float(f[0]), float(f[1])))
            except ValueError: pass
    return o


# strip the per-cell enable cards; the sweep re-emits them per code
base = [l for l in NETLIST.read_text().splitlines()
        if not l.strip().upper().startswith(("VCI", "VCQ"))
        and not l.strip().lower().startswith(".end")]

print(f"thermometer PI: {N_CELLS} unit cells per phase, {N_CELLS+1} codes")
print(f"{1/PERIOD/1e6:.0f} MHz, Q at +{Q_SHIFT*1e12:.0f} ps, edges 700 ps (overlapping)")
print()

rows = []
for code in range(N_CELLS + 1):
    d = OUT / f"c{code}"; d.mkdir(exist_ok=True)
    enables = []
    for i in range(N_CELLS):
        enables.append(f"VCI{i} ci{i} 0 DC {VB_ON if i < code else 0.0:.3f}")
        enables.append(f"VCQ{i} cq{i} 0 DC {0.0 if i < code else VB_ON:.3f}")
    step = PERIOD / 4000.0
    deck = base + enables + [".control",
                             f"tran {step:.12e} {T_END:.12e} 0 {step:.12e}",
                             f"wrdata {d}/out.txt v(vout)", ".endc", ".end"]
    (d / "pi.cir").write_text("\n".join(deck) + "\n")
    r = subprocess.run([str(NGSPICE), "-b", str(d / "pi.cir")],
                       capture_output=True, text=True, timeout=600)
    if not (d / "out.txt").exists():
        print(f"  code {code}: ngspice failed -- {r.stderr[-200:] or r.stdout[-200:]}")
        continue
    tr = [p for p in read(d / "out.txt") if p[0] >= 3 * PERIOD]
    if not tr:
        print(f"  code {code}: empty"); continue
    vs = [v for _, v in tr]
    swing = max(vs) - min(vs)
    vth = (max(vs) + min(vs)) / 2.0
    cr = [(t, dd) for t, dd in crossings(tr, vth) if dd == "fall"]
    if len(cr) < 3:
        print(f"  code {code}: {len(cr)} edges, swing {swing*1e3:.0f} mV"); continue
    ph = [(t % PERIOD) / PERIOD for t, _ in cr]
    ref = ph[0]
    ph = [p - 1.0 if p - ref > 0.5 else (p + 1.0 if ref - p > 0.5 else p) for p in ph]
    rows.append((code, statistics.mean(ph) * PERIOD * 1e12,
                 statistics.pstdev(ph) * PERIOD * 1e12, swing))
    print(f"  code {code}: phase {rows[-1][1]:7.1f} ps   swing {swing*1e3:5.1f} mV   "
          f"jitter {rows[-1][2]:.2f} ps", flush=True)

if len(rows) < 3:
    print("\nnot enough codes resolved"); raise SystemExit(1)

print()
print("  code   phase(ps)   step(ps)   swing(mV)")
print("  " + "-" * 42)
steps = []
prev = None
for c, ph, jit, sw in rows:
    s = "" if prev is None else f"{ph-prev:8.1f}"
    if prev is not None: steps.append(ph - prev)
    print(f"  {c:4d}   {ph:8.1f}  {s:>9}   {sw*1e3:8.1f}")
    prev = ph

total = rows[-1][1] - rows[0][1]
ideal = total / len(steps)
inl, acc = [], 0.0
for s in steps:
    acc += s - ideal
    inl.append(acc)
dnl_worst = max(steps, key=lambda s: abs(s - ideal)) - ideal
print()
print(f"  total phase moved : {total:+.1f} ps  (I/Q separation is {Q_SHIFT*1e12:.0f} ps)")
print(f"  mean step (1 LSB) : {ideal:+.1f} ps")
print(f"  DNL worst         : {dnl_worst:+.1f} ps  ({dnl_worst/abs(ideal):+.2f} LSB)")
print(f"  INL worst         : {max(inl, key=abs):+.1f} ps  ({max(inl, key=abs)/abs(ideal):+.2f} LSB)")
print(f"  swing variation   : {(max(r[3] for r in rows)-min(r[3] for r in rows))*1e3:.1f} mV "
      f"<- constant tail current should keep this small")
with (OUT / "phase_vs_code.csv").open("w") as fh:
    fh.write("code,phase_ps,jitter_ps,swing_V\n")
    for c, ph, jit, sw in rows:
        fh.write(f"{c},{ph:.4f},{jit:.4f},{sw:.6f}\n")
print(f"  csv: {OUT}/phase_vs_code.csv")
