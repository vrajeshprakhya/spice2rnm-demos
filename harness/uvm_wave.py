#!/usr/bin/env python3
"""The UVM-MS run as waveforms: what the verification environment drove
into the model, what came out, and what ngspice says each check should
have read.

The generated environment checks the model two ways. DC: it steps the
input to a level, waits until the output stops moving, and reads the
output once. AC: it plays a small sine about the bias, lets it settle,
then measures gain and phase over whole cycles (a lock-in: multiply by a
sine and a cosine and average). Each reading is compared with ngspice's
measurement of the circuit. The scoreboard prints verdicts; this draws
the run they came from.

It re-runs the generated environment in a scratch copy, changing one
thing: three lines added to the copy of top_<name>_ms.sv ask xezim to
record the top module's nets (the stimulus net and the response net the
bridge drives and senses). Everything else, including the verdicts this
page quotes, comes from that run's own log.

Two quirks of xezim this works around, both checked on the installed
build: only the FIRST $dumpvars call takes effect, and a second top-level
module (a separate dump module) makes UVM die at time 0 with
UVM/BAD_TOP. Hence one $dumpvars, inside the existing top.

usage: uvm_wave.py lpf2 [--out DIR] [--reuse]
       --reuse  draw from the last recorded run instead of simulating
"""
import argparse
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from wave_page import write_spec_page

HOME = Path.home()
RUNS = HOME / "s2r_runs"
XEZIM = Path(os.environ.get("XEZIM", HOME / "xezim/target/release/xezim"))
UVM_SRC = os.environ.get("UVM_SRC", str(HOME / "iverilog-unified/uvm-core/src"))
UVM_MS = os.environ.get("UVM_MS_LIB", str(HOME / "uvm_ms_demo/ms"))

COLORS = {"vin": "#9aa4ae", "circuit": "#5b8fd6", "model": "#c4471d",
          "error": "#7a4fb5"}

CASES = {
    "lpf2": {"env": RUNS / "lpf2",
             "title": "The UVM-MS run on the two-pole RC filter's model"},
}

DUMP = '''
  // Added by harness/uvm_wave.py to a COPY of this file (the generated
  // environment is not edited): record the stimulus and response nets.
  initial begin
    $dumpfile("uvm_wave.vcd");
    $dumpvars(1, top);
  end

endmodule : top'''


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------
def env_name(env):
    runners = sorted(env.glob("run_*_ms.sh"))
    if len(runners) != 1:
        raise SystemExit("expected one run_*_ms.sh in %s, found %d: run the "
                         "demo (spice2rnm --emit-uvm-ms) first"
                         % (env, len(runners)))
    return runners[0].name[len("run_"):-len("_ms.sh")]


def run_env(env, name, run, wall):
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    for f in list(env.glob("*.sv")) + list(env.glob("*.svh")):
        shutil.copy2(f, run)
    shutil.copy2(env / ("run_%s_ms.sh" % name), run)
    top = run / ("top_%s_ms.sv" % name)
    src = top.read_text()
    if src.count("\nendmodule : top") != 1:
        raise SystemExit("%s: cannot find the end of module top" % top)
    top.write_text(src.replace("\nendmodule : top", DUMP))
    wrapper = run / "xezim_wave"
    wrapper.write_text('#!/usr/bin/env bash\nexec "%s" --wave "$@"\n' % XEZIM)
    wrapper.chmod(0o755)
    envv = dict(os.environ, XEZIM=str(wrapper), UVM_SRC=UVM_SRC,
                UVM_MS_LIB=UVM_MS, WALL_TIMEOUT=str(wall))
    with open(run / "uvm.log", "w") as log:
        r = subprocess.run(["bash", "run_%s_ms.sh" % name,
                            "+UVM_VERBOSITY=UVM_HIGH"],
                           cwd=run, env=envv, stdout=log,
                           stderr=subprocess.STDOUT)
    return r.returncode


# --------------------------------------------------------------------------
# what the run wrote
# --------------------------------------------------------------------------
def read_vcd(path, names=("ain_net", "aout_net")):
    """The named nets of scope top, as {name: [(t_s, v)]}. Streams the
    file: the other few hundred variables are UVM bookkeeping."""
    ids, out, depth, t = {}, {n: [] for n in names}, 0, 0.0
    scale = 1e-15
    with open(path) as f:
        for line in f:
            if line.startswith("$enddefinitions"):
                break
            w = line.split()
            if not w:
                continue
            if w[0] == "$timescale":
                ts = " ".join(w[1:]).replace("$end", "").strip() or next(f).strip()
                m = re.match(r"(\d+)\s*(s|ms|us|ns|ps|fs)", ts)
                scale = int(m.group(1)) * {"s": 1, "ms": 1e-3, "us": 1e-6,
                                           "ns": 1e-9, "ps": 1e-12,
                                           "fs": 1e-15}[m.group(2)]
            elif w[0] == "$scope":
                depth += 1
            elif w[0] == "$upscope":
                depth -= 1
            elif w[0] == "$var" and depth == 1 and w[4] in names:
                ids[w[3]] = w[4]
        for line in f:
            c = line[:1]
            if c == "#":
                t = int(line[1:]) * scale
            elif c in "rR":
                v, _, i = line[1:].rstrip("\n").partition(" ")
                n = ids.get(i)
                if n:
                    out[n].append((t, float(v)))
    for n in names:
        if not out[n]:
            raise SystemExit("%s holds no %s: the dump did not record it"
                             % (path, n))
    return out


LINE = re.compile(r"@ (\d+): \S+ \[(DC_CHECK|AC_CHECK|AC_PHASE)\] "
                  r"(PASS|FAIL) (.*)$")
NUM = r"(-?[0-9.]+(?:e[-+]?\d+)?)"


def read_log(path):
    checks, summary, ac_phase = [], [], {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if "[SB_SUMMARY]" in line:
            # not UVM's "report counts by id" line, which also names it
            if "checks=" in line:
                summary.append(line.split("[SB_SUMMARY]", 1)[1].strip())
            continue
        m = LINE.search(line)
        if not m:
            continue
        t = int(m.group(1)) * 1e-15
        kind, verdict, rest = m.group(2), m.group(3), m.group(4)
        if kind == "DC_CHECK":
            g = re.match(r"in = %s V: ngspice %s V, model %s V, err %s V"
                         % (NUM, NUM, NUM, NUM), rest)
            checks.append({"kind": "dc", "t": t, "verdict": verdict,
                           "level": float(g.group(1)),
                           "gold": float(g.group(2)),
                           "model": float(g.group(3)),
                           "err": float(g.group(4))})
        elif kind == "AC_CHECK":
            g = re.match(r"f = %s Hz: ngspice %s dB, model %s dB, err %s dB"
                         % (NUM, NUM, NUM, NUM), rest)
            checks.append({"kind": "ac", "t": t, "verdict": verdict,
                           "f": float(g.group(1)),
                           "gold_db": float(g.group(2)),
                           "model_db": float(g.group(3)),
                           "err_db": float(g.group(4))})
        else:  # AC_PHASE is only printed when it fails
            g = re.match(r"f = %s Hz: ngspice %s deg, model %s deg"
                         % (NUM, NUM, NUM), rest)
            # (ngspice, model, verdict). Only failures were logged before
            # spice2rnm #74; passes are too since.
            ac_phase[t] = (float(g.group(2)), float(g.group(3)), verdict)
    return checks, summary, ac_phase


def read_tables(pkg, core):
    """The ngspice goldens and tolerances the scoreboard holds, and the
    bridge core's measurement settings, read from the generated files."""
    src = Path(pkg).read_text()

    def table(fn):
        m = re.search(r"function automatic real %s\(.*?endfunction" % fn,
                      src, re.S)
        if not m:
            return []
        rows = re.findall(r"(\d+)\s*:\s*%s\s*=\s*%s;" % (fn, NUM), m.group(0))
        return [float(v) for _, v in sorted(rows, key=lambda r: int(r[0]))]

    def const(name):
        m = re.search(r"localparam\s+(?:real|int)\s+%s\s*=\s*%s;"
                      % (name, NUM), src)
        return float(m.group(1)) if m else None

    csrc = Path(core).read_text()

    def param(name):
        m = re.search(r"parameter\s+(?:real|int)\s+%s\s*=\s*%s" % (name, NUM),
                      csrc)
        return float(m.group(1))

    return {"ac_freq": table("ac_freq"), "ac_phase": table("ac_phase_deg"),
            "tol_abs": const("TOL_ABS"), "tol_db": const("TOL_DB"),
            "tol_deg": const("TOL_DEG"), "ac_ampl": const("AC_AMPL"),
            "ac_bias": const("AC_BIAS"),
            "spc": int(param("AC_SAMPLES_PER_CYCLE")),
            "meas_cycles": int(param("AC_MEAS_CYCLES")),
            "settle_cycles": int(param("AC_SETTLE_CYCLES")),
            "settle_step": param("SETTLE_STEP_FS") * 1e-15,
            # Since spice2rnm #74 the bridge reads each AC sample at the
            # middle of its drive step (#(dt_fs / 2.0); v = aout), which
            # removes the 2.8 degree lead reading at the end used to add.
            "midstep": bool(re.search(r"#\(dt_fs\s*/\s*2(\.0)?\);\s*\n\s*v\s*=\s*aout",
                                      csrc))}


# --------------------------------------------------------------------------
# the measurements, redone from the recording
# --------------------------------------------------------------------------
def held(tr, t, eps=1e-18):
    """The value a reader sees at time t: the last change at or before it
    (a real-valued net holds its value between changes)."""
    lo, hi = 0, len(tr) - 1
    if t < tr[0][0]:
        return tr[0][1]
    while hi - lo > 1:
        m = (lo + hi) // 2
        if tr[m][0] <= t + eps:
            lo = m
        else:
            hi = m
    return tr[hi][1] if tr[hi][0] <= t + eps else tr[lo][1]


def lockin(out, chk, tb):
    """Re-measure one AC check exactly as the bridge core does: one
    sample per 1/spc of a cycle over meas_cycles, multiplied by sin and
    cos of the drive's phase at the start of that sample's step and
    averaged. Where in the step the sample is taken follows the bridge:
    at its END on a bridge from before spice2rnm #74 (the last sample at
    the moment the check was logged), at its MIDDLE since (the last one
    half a step before)."""
    spc, n = tb["spc"], tb["spc"] * tb["meas_cycles"]
    period = 1.0 / chk["f"]
    dt = period / spc
    off = dt / 2 if tb.get("midstep") else 0.0
    t_end = chk["t"]
    acc_i = acc_q = acc_m = 0.0
    for k in range(n):
        v = held(out, t_end - off - (n - 1 - k) * dt)
        th = 2 * math.pi * k / spc
        acc_q += v * math.sin(th)
        acc_i += v * math.cos(th)
        acc_m += v
    amp = 2 * math.hypot(acc_i, acc_q) / n
    return {"db": 20 * math.log10(amp / tb["ac_ampl"]),
            "deg": math.degrees(math.atan2(acc_i, acc_q)),
            "mean": acc_m / n, "t0": t_end - off - (n - 1) * dt, "dt": dt,
            "period": period}


def wrap180(d):
    while d > 180:
        d -= 360
    while d < -180:
        d += 360
    return d


def thin(tr, q=1e7):
    """Drop the inside of every run of equal values (at the page's 0.1 uV
    resolution): a held level keeps its first and last point, so nothing
    the page can show is lost."""
    if len(tr) < 3:
        return tr
    qs = [round(v * q) for _, v in tr]
    out = [tr[0]]
    for k in range(1, len(tr) - 1):
        if qs[k] != qs[k - 1] or qs[k] != qs[k + 1]:
            out.append(tr[k])
    out.append(tr[-1])
    return out


def fmt_f(f):
    return ("%.4g MHz" % (f / 1e6)) if f >= 1e6 else ("%.4g kHz" % (f / 1e3))


def fmt_t(t):
    return ("%.3f µs" % (t * 1e6)) if t >= 1e-6 else ("%.1f ns" % (t * 1e9))


# --------------------------------------------------------------------------
def main():
    if sys.argv[1:] == ["--cases"]:  # for refresh.sh: which cases have a page
        print(" ".join(sorted(CASES)))
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case", choices=sorted(CASES))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--wall", type=int, default=3600)
    a = ap.parse_args()
    case = CASES[a.case]
    env = case["env"]
    name = env_name(env)
    out = a.out or RUNS / ("%s_wave" % a.case)
    out.mkdir(parents=True, exist_ok=True)
    run = RUNS / ("%s_uvmwave" % a.case) / "run"

    if not (a.reuse and (run / "uvm_wave.vcd").exists()):
        print("  re-running the UVM-MS environment with a recording "
              "(a few minutes: recording every model step slows xezim)")
        rc = run_env(env, name, run, a.wall)
        if rc:
            raise SystemExit("the UVM-MS run exited %d; see %s"
                             % (rc, run / "uvm.log"))
    checks, summary, phase_log = read_log(run / "uvm.log")
    phase_fails = {t for t, v in phase_log.items() if v[2] == "FAIL"}
    logged_phases = any(v[2] == "PASS" for v in phase_log.values())
    if not checks or not summary:
        raise SystemExit("%s has no scoreboard checks or summary: the run did "
                         "not finish" % (run / "uvm.log"))
    tb = read_tables(env / ("%s_ms_pkg.sv" % name),
                     env / ("%s_bridge_core.sv" % name))
    w = read_vcd(run / "uvm_wave.vcd")
    vin, vout = w["ain_net"], w["aout_net"]
    t_end = max(vin[-1][0], vout[-1][0])

    # --- the expectation trace, the marks, the windows -----------------
    expect, marks, shades = [], [], []
    worst_dev_db = 0.0
    n_dc = sum(c["kind"] == "dc" for c in checks)
    n_ac = sum(c["kind"] == "ac" for c in checks)
    k_dc = k_ac = 0
    worst = None
    for c in checks:
        if c["kind"] == "dc":
            k_dc += 1
            a0 = c["t"] - tb["settle_step"]
            expect += [(a0, c["gold"]), (c["t"], c["gold"]), (c["t"], None)]
            ratio = abs(c["err"]) / tb["tol_abs"]
            txt = ("DC check %d of %d at %s: input %.4f V. ngspice %.6f V, "
                   "model %.6f V, error %.3f mV against a %.1f mV tolerance: "
                   "%s" % (k_dc, n_dc, fmt_t(c["t"]), c["level"], c["gold"],
                           c["model"], c["err"] * 1e3, tb["tol_abs"] * 1e3,
                           c["verdict"]))
            marks += [
                {"t": c["t"], "panel": 0, "y": c["gold"], "color": "circuit",
                 "kind": "ring", "text": txt},
                {"t": c["t"], "panel": 0, "y": c["model"], "color": "model",
                 "kind": "dot", "text": txt},
                {"t": c["t"], "panel": 1, "y": ratio, "color": "error",
                 "kind": "dot", "text": txt},
            ]
        else:
            k_ac += 1
            mm = lockin(vout, c, tb)
            worst_dev_db = max(worst_dev_db, abs(mm["db"] - c["model_db"]))
            i = min(range(len(tb["ac_freq"])),
                    key=lambda j: abs(tb["ac_freq"][j] - c["f"]))
            gold_deg = tb["ac_phase"][i]
            model_deg = phase_log.get(c["t"], (None, mm["deg"]))[1]
            err_deg = abs(wrap180(model_deg - gold_deg))
            amp = tb["ac_ampl"] * 10 ** (c["gold_db"] / 20)
            ph = math.radians(gold_deg)
            t0, dt = mm["t0"], mm["dt"]
            npts = tb["meas_cycles"] * tb["spc"] * 4
            for k in range(npts + 1):
                t = t0 + (k / 4.0) * dt
                th = 2 * math.pi * (k / 4.0) / tb["spc"]
                expect.append((t, mm["mean"] + amp * math.sin(th + ph)))
            expect.append((c["t"], None))
            shades.append({"a": t0, "b": c["t"], "label": fmt_f(c["f"])})
            r_db = abs(c["err_db"]) / tb["tol_db"]
            r_deg = err_deg / tb["tol_deg"]
            txt = ("AC check %d of %d at %s, measured over %d cycles: gain "
                   "ngspice %.4f dB, model %.4f dB (error %.4f dB, tolerance "
                   "%.2f dB); phase ngspice %.2f°, model %.2f° "
                   "(error %.2f°, tolerance %.0f°): %s"
                   % (k_ac, n_ac, fmt_f(c["f"]), tb["meas_cycles"],
                      c["gold_db"], c["model_db"], abs(c["err_db"]),
                      tb["tol_db"], gold_deg, model_deg, err_deg,
                      tb["tol_deg"],
                      "FAIL" if c["verdict"] == "FAIL" or c["t"] in phase_fails
                      else "PASS"))
            c.update({"ratio_db": r_db, "ratio_deg": r_deg, "gold_deg": gold_deg,
                      "model_deg": model_deg, "t0": t0})
            marks += [
                {"t": c["t"], "panel": 1, "y": r_db, "color": "error",
                 "kind": "dot", "text": txt},
                {"t": c["t"], "panel": 1, "y": r_deg, "color": "error",
                 "kind": "ring", "text": txt},
            ]
        r = max(m["y"] for m in marks if m["t"] == c["t"] and m["panel"] == 1)
        if worst is None or r > worst[0]:
            worst = (r, c)
    if worst_dev_db > 0.01:
        raise SystemExit("re-measuring the AC checks from the recording "
                         "disagrees with the scoreboard by %.4f dB: the "
                         "recording is not what the scoreboard saw"
                         % worst_dev_db)
    expect.sort(key=lambda p: p[0])  # DC and AC segments interleave in time

    # --- presets ---------------------------------------------------------
    sweep_dc = [c for c in checks if c["kind"] == "dc"][:41]
    acs = [c for c in checks if c["kind"] == "ac"]
    presets = [{"label": "Whole run", "a": 0.0, "b": t_end}]
    if sweep_dc:
        presets.append({"label": "DC staircase", "a": 0.0,
                        "b": sweep_dc[-1]["t"] + 2 * tb["settle_step"]})
    if acs:
        lo = min(acs, key=lambda c: c["f"])
        hi = max(acs, key=lambda c: c["f"])
        for lab, c in (("Lowest tone", lo), ("Highest tone", hi)):
            # Ends AT the check: just after it the next check's input jumps,
            # and the stimulus (3.6 mV) dwarfs a filtered response, so the
            # view hides it and fits the axis to ngspice and the model.
            span = c["t"] - c["t0"]
            presets.append({"label": "%s (%s)" % (lab, fmt_f(c["f"])),
                            "a": c["t0"] - 0.03 * span, "b": c["t"],
                            "vin": False})
    wc = worst[1]
    if wc["kind"] == "dc":
        presets.append({"label": "Worst check", "a": wc["t"] - 3 * tb["settle_step"],
                        "b": wc["t"] + tb["settle_step"]})
    else:
        span = wc["t"] - wc["t0"]
        presets.append({"label": "Worst check", "a": wc["t0"] - 0.03 * span,
                        "b": wc["t"], "vin": False})

    # --- words ------------------------------------------------------------
    fails = sum(c["verdict"] == "FAIL" for c in checks) + len(phase_fails)
    score = ("%d DC checks and %d AC checks against ngspice, %d failed. "
             "Worst error: %.0f%% of its tolerance."
             % (n_dc, n_ac, fails, 100 * worst[0]))
    dc_levels = sorted({c["level"] for c in checks if c["kind"] == "dc"})
    freqs = sorted({c["f"] for c in acs})
    notes = [
        "What the run does: it steps the model's input through %d levels "
        "from %.2f to %.2f V, waits at each until the output stops moving "
        "(steps of %.0f ns until two in a row change it by less than the "
        "settling limit) and reads the output once. Then it plays a small "
        "sine, %.1f mV on top of %.2f V, at %d frequencies from %s to %s: "
        "%d cycles to settle, then gain and phase measured over the next %d. "
        "A randomised tail repeats points of either kind. The input is "
        "built from steps, %d per cycle, so the sines going in are "
        "staircases: that is what the model actually receives."
        % (len(dc_levels), dc_levels[0], dc_levels[-1],
           tb["settle_step"] * 1e9, tb["ac_ampl"] * 1e3, tb["ac_bias"],
           len(freqs), fmt_f(freqs[0]), fmt_f(freqs[-1]),
           tb["settle_cycles"], tb["meas_cycles"], tb["spc"])
        if acs and dc_levels else "",
        "Every reading is compared with what ngspice measured on the "
        "circuit: the DC levels from a DC sweep, the gain and phase from an "
        "AC analysis. Blue is ngspice, red is the model. At a DC check the "
        "blue ring is ngspice's value and the red dot is the model's "
        "reading. In an AC window (shaded, labelled with its frequency) the "
        "blue band is the sine ngspice's gain and phase predict for this "
        "drive, centred on the model's own average level there (the level "
        "is the DC checks' business); the red line is what the model did.",
        "The lower panel puts every check on one scale: its error divided "
        "by its tolerance, so a point above the dashed line at 1 would be a "
        "failure. Dots are DC errors and AC gain errors, rings are AC phase "
        "errors. Hover over any point to read the check in full.",
        "The scoreboard's own summary for this run: " + "; ".join(summary)
        + ".",
        "A caution about the phase checks. The bridge holds each drive value "
        "for one step (1/%d of a cycle) and reads the output at the END of "
        "the step, but scores that reading against the drive's phase at the "
        "step's START. That alone reads as a lead of about 360°/%d = "
        "%.1f° at every frequency, before the model contributes "
        "anything, and every phase error above includes it. A model that "
        "lags a little (as a sampled model does) can therefore look better "
        "than it is, because the two cancel."
        % (tb["spc"], 2 * tb["spc"], 360.0 / (2 * tb["spc"]))
        if acs and not tb["midstep"] else "",
        "How the phase checks read. The bridge holds each drive value for "
        "one step (1/%d of a cycle) and reads the output at the MIDDLE of "
        "the step, where the held value stands for the sine, so the reading "
        "and the drive phase it is scored against describe the same instant "
        "(spice2rnm #74: reading at the step's end used to add a lead of "
        "360°/%d = %.1f° to every check)."
        % (tb["spc"], 2 * tb["spc"], 360.0 / (2 * tb["spc"]))
        if acs and tb["midstep"] else "",
        "How this page was made: the generated environment was re-run "
        "unchanged except for three lines added to a copy of top_%s_ms.sv "
        "that record its stimulus and response nets. Every check above is "
        "that run's own log line%s. This page also re-measures each AC "
        "window from the recording the way the bridge does; its gains agree "
        "with the scoreboard's to within %.1e dB, which is the check that "
        "the recording is what the scoreboard saw."
        % (name, " (phases included)" if logged_phases else
           "; a passing AC phase is not in this run's log, so the phases "
           "above are the page's own re-measurement", worst_dev_db),
    ]
    spec = {
        "title": case["title"], "score": score,
        "notes": [n for n in notes if n],
        "help": ("Drag across the plot to zoom into that stretch. Scroll to "
                 "zoom around the pointer, Shift+scroll (or the arrow keys) "
                 "to slide along the run, double-click to see the whole run "
                 "again. Hover over a check to read it."),
        "footer": ("Every point the run recorded is in this page (times to "
                   "1 fs, voltages to 0.1 µV), and it loads nothing from "
                   "the network. Built by harness/uvm_wave.py in the "
                   "spice2rnm demos."),
        "traces": [
            {"key": "vin", "label": "stimulus", "pts": thin(vin),
             "color": "vin", "w": 1.2, "a": 1},
            {"key": "expect", "label": "ngspice expects",
             "legend": "what ngspice says the check should read",
             "pts": expect, "color": "circuit", "w": 6, "a": 0.45},
            {"key": "model", "label": "model", "legend": "model (xezim)",
             "pts": thin(vout), "color": "model", "w": 1.6, "a": 1},
        ],
        "panels": [
            {"id": "p-main", "ylabel": "volts",
             "keys": ["vin", "expect", "model"], "height": 340},
            {"id": "p-ratio", "ylabel": "error ÷ tolerance", "keys": [],
             "ratio": True, "height": 170},
        ],
        "marks": marks, "shades": shades,
        "hlines": [{"panel": 1, "y": 1.0, "label": "fail line"}],
        "legend_marks": [
            {"color": "model", "kind": "dot", "label": "model's reading"},
            {"color": "circuit", "kind": "ring", "label": "ngspice value"},
            {"color": "error", "kind": "dot",
             "label": "error ÷ tolerance (ring: AC phase)"},
        ],
        "presets": presets, "t1": t_end,
    }
    page = out / ("%s_uvm.html" % a.case)
    size = write_spec_page(page, spec, COLORS)
    readme = out / "README.txt"
    if readme.exists():
        title = "The UVM-MS run (act 6), as waveforms"
        base = readme.read_text()
        if title in base:  # a re-run replaces its own section
            base = base[:base.index(title)]
        readme.write_text(base.rstrip("\n") + "\n\n" + "\n".join([
            title, "-" * len(title),
            "%s: open it in any browser. It shows what the UVM-MS environment "
            "drove into the model, what came out, and at every scoreboard "
            "check what ngspice says the reading should be." % page.name,
            "Verdicts: %s" % score,
            "Recorded by re-running the generated environment with three "
            "lines added to a copy of top_%s_ms.sv; the checks are that "
            "run's own log lines. AC gains re-measured from the recording "
            "agree with the scoreboard's to within %.1e dB." % (name, worst_dev_db),
            ("The bridge reads each AC sample at the middle of its drive "
             "step, so the phases carry no read bias of their own."
             if tb["midstep"] else
             "Caution: the bridge reads each AC sample at the end of a drive "
             "step but scores it against the phase at the step's start, a "
             "lead of about %.1f deg included in every phase error."
             % (360.0 / (2 * tb["spc"]))), ""]))
    print("  %-22s %6.2f MB   %s" % (page.name, size / 1e6, score))
    print("  AC re-measured from the recording: within %.1e dB of the "
          "scoreboard" % worst_dev_db)


if __name__ == "__main__":
    sys.exit(main())
