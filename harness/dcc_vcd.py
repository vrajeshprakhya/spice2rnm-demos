#!/usr/bin/env python3
"""DCC waveform: the same 60%-duty clock through SPICE and through the model,
in one VCD, with the residual as its own trace.

The pipeline's own equivalence VCD for this block is a CHIRP run -- 160 MB of
smooth small-signal response that shows nothing about edges. Duty is the whole
function of this circuit, so the waveform worth looking at is a clock going in
and a clock coming out.

Also reports the duty each side produces, which is the number an rms voltage
comparison cannot see.
"""
import subprocess, statistics
from pathlib import Path

HOME = Path.home()
NGSPICE = HOME / "ngspice-install/bin/ngspice"
XEZIM = HOME / "xezim/target/release/xezim"
NETLIST = HOME / "spice2rnm/work/dcc.cir"
RNM = HOME / "s2r_runs/dcc2/dcc_rnm.sv"
OUT = HOME / "s2r_runs/dcc2_vcd"
OUT.mkdir(parents=True, exist_ok=True)

PERIOD = 2e-9          # 500 MHz
N_CYC = 24
T_END = N_CYC * PERIOD
# vctrl stays at the netlist's 0.90 V, which is what the model was
# characterised at -- the RNM is a function of clk alone, with the threshold
# baked in, so comparing at any other vctrl would be comparing two circuits.
CLK = "VCLK clk 0 PULSE(0.5 1.3 0 400p 400p 800p 2n)"


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


def sv_real(x, sig=9):
    s = f"{float(x):.{sig}g}"
    return s if any(c in s for c in ".eE") else s + ".0"


def read(p):
    o = []
    for line in Path(p).read_text().split("\n"):
        f = line.split()
        if len(f) >= 2:
            try: o.append((float(f[0]), float(f[1])))
            except ValueError: pass
    return o


if not RNM.exists():
    raise SystemExit(f"no model at {RNM} -- run demo_2_dcc.sh first")

# --- ngspice reference ----------------------------------------------------
deck = [l for l in NETLIST.read_text().splitlines()
        if not l.strip().upper().startswith("VCLK ")
        and not l.strip().lower().startswith(".end")]
step = PERIOD / 2000.0
deck += [CLK, ".control",
         f"tran {step:.12e} {T_END:.12e} 0 {step:.12e}",
         f"wrdata {OUT}/spice.txt v(vout)", ".endc", ".end"]
(OUT / "clk.cir").write_text("\n".join(deck) + "\n")
print("running ngspice ...", flush=True)
subprocess.run([str(NGSPICE), "-b", str(OUT / "clk.cir")],
               capture_output=True, text=True, timeout=900)
spice = read(OUT / "spice.txt")
print(f"  {len(spice)} reference points")

# --- the same clock, as PWL points for the testbench -----------------------
pts = []
for i in range(N_CYC):
    t0 = i * PERIOD
    pts += [(t0, 0.5), (t0 + 400e-12, 1.3),
            (t0 + 1.2e-9, 1.3), (t0 + 1.6e-9, 0.5),
            (t0 + PERIOD - 1e-15, 0.5)]
clean = []
for t, v in pts:
    if clean and t <= clean[-1][0]: t = clean[-1][0] + 1e-15
    clean.append((t, v))
pts = clean

VCD = OUT / "tb_dcc.vcd"
tb = ["`timescale 1fs/1fs", "module tb;",
      "  real in_val, out_val;",
      "  real spice_ref, err;",
      "  dcc_rnm dut(.in_val(in_val), .out_val(out_val));",
      "",
      "  always @(out_val, spice_ref) err = out_val - spice_ref;",
      "",
      "  initial begin",
      f'    $dumpfile("{VCD}");',
      "    $dumpvars(1, tb);",   # depth 1: keep the file small for a live demo
      "  end",
      "",
      "  initial begin"]
prev = 0.0
for t, v in spice:
    tfs = t * 1e15
    if tfs - prev > 0: tb.append(f"    #({tfs-prev:.6f});")
    tb.append(f"    spice_ref = {sv_real(v)};")
    prev = tfs
tb += ["  end", "", "  initial begin"]
prev = 0.0
for t, v in pts:
    tfs = t * 1e15
    if tfs - prev > 0: tb.append(f"    #({tfs-prev:.6f});")
    tb.append(f"    in_val = {sv_real(v)};")
    prev = tfs
tb += [f"    #({PERIOD*1e15:.6f});", "    $finish;", "  end", "endmodule"]
(OUT / "tb_dcc.sv").write_text("\n".join(tb) + "\n")

print("running xezim ...", flush=True)
r = subprocess.run([str(XEZIM), str(RNM), str(OUT / "tb_dcc.sv"),
                    "-o", str(OUT / "model.txt")],
                   capture_output=True, text=True, timeout=1800)
if not VCD.exists():
    print("no vcd:\n", r.stdout[-1500:], r.stderr[-1500:]); raise SystemExit(1)

# --- duty, both sides -----------------------------------------------------
warm = 4 * PERIOD
sp = [p for p in spice if p[0] >= warm]
vs = [v for _, v in sp]
vth = (max(vs) + min(vs)) / 2.0
ds = duty(crossings(sp, vth))

print()
print(f"  vcd: {VCD.stat().st_size/1e6:.1f} MB   {VCD}")
print(f"  input clock duty : 60.00 %   (deliberately skewed)")
if ds:
    print(f"  SPICE output duty: {statistics.mean(ds)*100:.2f} %   "
          f"at vctrl = 0.90 V")
print()
print("  open it:")
print(f"    gtkwave {VCD}")
print("  then for spice_ref / out_val / err:")
print("    right-click -> Data Format -> Analog -> Interpolated")
