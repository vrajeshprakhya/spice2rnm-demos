#!/usr/bin/env python3
"""DCC demo: the corrector's actuator characteristic.

Sweeps the threshold control and measures the OUTPUT DUTY of a clock that
arrives at 60%. The curve is what a duty-cycle-correction loop servos
along, and where it crosses 50% is the point the loop would settle to.

Duty is not visible to an rms-voltage comparison, which is the whole
reason this block needed a timing metric.
"""
import subprocess, statistics
from pathlib import Path

HOME = Path.home()
NGSPICE = HOME / "ngspice-install/bin/ngspice"
NETLIST = HOME / "spice2rnm/work/dcc.cir"
OUT = HOME / "s2r_runs/demo_dcc"
OUT.mkdir(parents=True, exist_ok=True)

PERIOD = 2e-9
N_CYC = 14
T_END = N_CYC * PERIOD
# Extended upward: the first sweep (0.72..1.08) reached only 45.8% and never
# crossed 50%. The comparator INVERTS, so a 60%-duty input leaves as ~40%,
# and the threshold has to move well above mid-supply to trade enough of the
# falling edge back. Slope near the top was ~0.055 %/mV, putting the null
# around 1.16 V.
VC_LO, VC_HI, N = 0.90, 1.35, 16


def crossings(tr, vth):
    out = []
    for (t0, v0), (t1, v1) in zip(tr, tr[1:]):
        if (v0 < vth) != (v1 < vth) and v1 != v0:
            out.append((t0 + (t1 - t0) * (vth - v0) / (v1 - v0),
                        "rise" if v1 > v0 else "fall"))
    return out


def duty(cr):
    rises = [t for t, d in cr if d == "rise"]
    falls = [t for t, d in cr if d == "fall"]
    out = []
    for i in range(len(rises) - 1):
        f = [t for t in falls if rises[i] < t < rises[i + 1]]
        if f:
            out.append((f[0] - rises[i]) / (rises[i + 1] - rises[i]))
    return out


def read(p):
    o = []
    for line in Path(p).read_text().split("\n"):
        f = line.split()
        if len(f) >= 2:
            try: o.append((float(f[0]), float(f[1])))
            except ValueError: pass
    return o


# The netlist carries `VCLK ... DC 0.9 AC 0.01` so the pipeline can
# characterise it; for these transient sweeps we substitute the actual clock.
CLK_PULSE = "VCLK clk 0 PULSE(0.5 1.3 0 400p 400p 800p 2n)"
base = [l for l in NETLIST.read_text().splitlines()
        if not l.strip().upper().startswith(("VCTRL ", "VCLK "))
        and not l.strip().lower().startswith(".end")] + [CLK_PULSE]

print("DCC actuator characteristic -- input clock is 60% duty, 500 MHz")
print("sweeping the threshold control; where output duty crosses 50% is the null")
print()
rows = []
for k in range(N):
    vc = VC_LO + (VC_HI - VC_LO) * k / (N - 1)
    d = OUT / f"v{k:02d}"; d.mkdir(exist_ok=True)
    step = PERIOD / 4000.0
    deck = base + [f"VCTRL vctrl 0 DC {vc:.6f}", ".control",
                   f"tran {step:.12e} {T_END:.12e} 0 {step:.12e}",
                   f"wrdata {d}/out.txt v(vout)", ".endc", ".end"]
    (d / "d.cir").write_text("\n".join(deck) + "\n")
    subprocess.run([str(NGSPICE), "-b", str(d / "d.cir")],
                   capture_output=True, text=True, timeout=600)
    if not (d / "out.txt").exists():
        print(f"  vctrl={vc:.3f}  ngspice failed"); continue
    tr = [p for p in read(d / "out.txt") if p[0] >= 3 * PERIOD]
    if not tr: continue
    vs = [v for _, v in tr]
    swing = max(vs) - min(vs)
    if swing < 0.2:
        print(f"  vctrl={vc:.3f}  output not switching (swing {swing*1e3:.0f} mV)")
        rows.append((vc, None, swing)); continue
    ds = duty(crossings(tr, (max(vs) + min(vs)) / 2))
    if not ds:
        print(f"  vctrl={vc:.3f}  no complete cycles"); continue
    rows.append((vc, statistics.mean(ds), swing))
    print(f"  vctrl={vc:.3f}  duty {statistics.mean(ds)*100:6.2f}%   "
          f"swing {swing:.3f} V", flush=True)

good = [(v, d) for v, d, s in rows if d is not None]
print()
if len(good) >= 2:
    print("  vctrl(V)   duty(%)   from 50%")
    print("  " + "-" * 34)
    for v, d in good:
        print(f"  {v:7.3f}   {d*100:6.2f}   {(d-0.5)*100:+7.2f}")
    # where does it cross 50%?
    null = None
    for (v0, d0), (v1, d1) in zip(good, good[1:]):
        if (d0 - 0.5) * (d1 - 0.5) <= 0 and d1 != d0:
            null = v0 + (v1 - v0) * (0.5 - d0) / (d1 - d0)
            break
    print()
    if null is not None:
        print(f"  50% duty null at vctrl = {null:.4f} V  <- the loop's operating point")
    else:
        print(f"  no 50% crossing in {VC_LO}..{VC_HI} V "
              f"(duty spans {min(d for _, d in good)*100:.1f}%..{max(d for _, d in good)*100:.1f}%)")
    span = (max(d for _, d in good) - min(d for _, d in good)) * 100
    print(f"  correction range: {span:.1f} percentage points of duty")
with (OUT / "duty_vs_ctrl.csv").open("w") as fh:
    fh.write("vctrl_V,duty,swing_V\n")
    for v, d, s in rows:
        fh.write(f"{v:.6f},{'' if d is None else f'{d:.6f}'},{s:.6f}\n")
print(f"  csv: {OUT}/duty_vs_ctrl.csv")
