#!/usr/bin/env python3
"""Whose is the AC phase error: the model's, or the testbench's?

The UVM-MS bridge drives each AC check as a staircase (64 steps per
cycle) and scores each reading against the drive's phase at the
step's START. Before spice2rnm #74 it read at the step's END, which
alone reads as a lead of about 360/128 = 2.8 degrees whatever is being
measured; since #74 it reads at the step's MIDDLE. This script reads
the generated bridge and follows whichever it does.

This drives the IDEAL two-section RC filter (R and C read from
netlists/rc_lpf2.cir, solved exactly, step by step, with the matrix
exponential) with the same staircase, reads it the same way, and sets it
beside ngspice's golden and the model's reading from the recorded run
(harness/uvm_wave.py lpf2 must have run first). The columns:

  ngspice      the .ac golden the scoreboard holds
  ideal        the ideal circuit, read by the bridge's method
  model        the model, read by the bridge's method (from the recording)
  bench        ideal - ngspice: the testbench's own offset
  scoreboard   model - ngspice: what the scoreboard judges
  model own    model - ideal: the model's error with the offset removed

usage: uvm_phase_split.py        (lpf2 only)
"""
import math
import re
import sys
from pathlib import Path

from uvm_wave import RUNS, lockin, read_log, read_tables, read_vcd, wrap180

HERE = Path(__file__).resolve().parent


def value(tok):
    m = re.fullmatch(r"([0-9.]+)([a-zA-Z]*)", tok)
    mult = {"": 1, "k": 1e3, "meg": 1e6, "m": 1e-3, "u": 1e-6, "n": 1e-9,
            "p": 1e-12, "f": 1e-15}[m.group(2).lower()]
    return float(m.group(1)) * mult


def ladder(netlist):
    """R1, C1, R2, C2 of the two-section ladder."""
    parts = {}
    for line in Path(netlist).read_text().splitlines():
        w = line.split()
        if len(w) >= 4 and w[0].upper() in ("R1", "R2", "C1", "C2"):
            parts[w[0].upper()] = value(w[3])
    return parts["R1"], parts["C1"], parts["R2"], parts["C2"]


def expm2(M, h):
    """exp(M h) for a 2x2 matrix with real distinct eigenvalues."""
    p, q, r, s = M[0][0], M[0][1], M[1][0], M[1][1]
    tr, det = p + s, p * s - q * r
    disc = math.sqrt(tr * tr / 4 - det)
    l1, l2 = tr / 2 + disc, tr / 2 - disc
    k1, k2 = math.exp(l1 * h) / (l1 - l2), math.exp(l2 * h) / (l1 - l2)
    return [[k1 * (p - l2) - k2 * (p - l1), (k1 - k2) * q],
            [(k1 - k2) * r, k1 * (s - l2) - k2 * (s - l1)]]


def ideal_reading(R1, C1, R2, C2, f, ampl, bias, spc, settle, meas,
                  midstep=False):
    # state (v_mid, v_out); a constant input u is also each node's steady state
    A = [[-(1 / R1 + 1 / R2) / C1, 1 / (R2 * C1)], [1 / (R2 * C2), -1 / (R2 * C2)]]
    E = expm2(A, 1 / f / spc)
    Eh = expm2(A, 1 / f / spc / 2)   # half a step, for a mid-step read
    x = [bias, bias]
    acc_i = acc_q = 0.0
    for n in range(spc * (settle + meas)):
        th = 2 * math.pi * (n % spc) / spc
        u = bias + ampl * math.sin(th)
        def adv(x, M):
            d = [x[0] - u, x[1] - u]
            return [u + M[0][0] * d[0] + M[0][1] * d[1],
                    u + M[1][0] * d[0] + M[1][1] * d[1]]
        if midstep:                 # read at the MIDDLE of the step
            x = adv(x, Eh); v = x[1]; x = adv(x, Eh)
        else:                       # read at the END of the step
            x = adv(x, E); v = x[1]
        if n >= spc * settle:       # scored against the step's START phase
            acc_q += v * math.sin(th)
            acc_i += v * math.cos(th)
    return math.degrees(math.atan2(acc_i, acc_q))


def main():
    R1, C1, R2, C2 = ladder(HERE.parent / "netlists" / "rc_lpf2.cir")
    run, env = RUNS / "lpf2_uvmwave" / "run", RUNS / "lpf2"
    if not (run / "uvm_wave.vcd").exists():
        raise SystemExit("no recorded run: python3 harness/uvm_wave.py lpf2 first")
    checks, _, _ = read_log(run / "uvm.log")
    tb = read_tables(env / "rc_lpf2_ms_pkg.sv", env / "rc_lpf2_bridge_core.sv")
    out = read_vcd(run / "uvm_wave.vcd")["aout_net"]
    tstep = float(re.search(r"localparam real DT_SECONDS\s*=\s*([0-9.eE+-]+)",
                            (env / "rc_lpf2_rnm.sv").read_text()).group(1))
    print("R1=%g C1=%g R2=%g C2=%g; model time step %.4g ns; bridge reads at "
          "the %s of each step" % (R1, C1, R2, C2, tstep * 1e9,
                                   "MIDDLE" if tb["midstep"] else "END"))
    print("%10s %9s %9s %9s | %7s %10s %9s %13s"
          % ("f (Hz)", "ngspice", "ideal", "model", "bench", "scoreboard",
             "model own", "as a delay"))
    seen = set()
    for c in checks:
        if c["kind"] != "ac" or c["f"] in seen:
            continue
        seen.add(c["f"])
        i = min(range(len(tb["ac_freq"])), key=lambda j: abs(tb["ac_freq"][j] - c["f"]))
        gold = tb["ac_phase"][i]
        ideal = ideal_reading(R1, C1, R2, C2, c["f"], tb["ac_ampl"], tb["ac_bias"],
                              tb["spc"], tb["settle_cycles"], tb["meas_cycles"],
                              tb["midstep"])
        model = lockin(out, c, tb)["deg"]
        own = wrap180(model - ideal)
        print("%10.4g %9.2f %9.2f %9.2f | %7.2f %10.2f %9.2f %10.3f ns"
              % (c["f"], gold, ideal, model, wrap180(ideal - gold),
                 wrap180(model - gold), own, -own / 360 / c["f"] * 1e9))
    print("360/(2 x %d steps per cycle) = %.3f deg" % (tb["spc"], 180 / tb["spc"]))


if __name__ == "__main__":
    sys.exit(main())
