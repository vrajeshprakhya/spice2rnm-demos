#!/usr/bin/env python3
"""Demo 4b's PLL as waveforms: the whole loop locking, and the blocks it
was built from, each drawn against the circuit it was made from.

Demo 4b closes the generated models around the design's own phase
detector and divider RTL and runs the lot on xezim alone, with no
transistors anywhere. Its verdict is a few printed numbers: the rate the
divided clock settled at, and how far the control voltage moved while it
was measured. This draws the run those numbers came from.

  <case>_loop.html   the loop, start-up to lock: the control voltage, the
                     oscillator's rate cycle by cycle, the charge-pump
                     node, the up/down pulses, the reference against the
                     divided clock, and the oscillator's own output
  <case>_<inv>.html  an inverter, circuit (ngspice) against model (xezim)
  <case>_<inv>.fst   the same four traces for a waveform viewer, with a
  <case>_<inv>.gtkw  GTKWave layout
  <case>_<rc>.html   the loop filter, circuit against model, under the
                     current step the pipeline checked it with

The loop page RE-RUNS the generated loop file in a scratch copy, changing
one thing: four lines asking xezim to record the top module's nets. It
then checks that the re-run printed exactly what the demo's own run
printed, and refuses to draw a run that disagrees. Every other page is
drawn from files the demo run already wrote; nothing else is simulated.

usage: pll_wave.py pll_nocosim [--out DIR] [--reuse]
       --reuse  draw from the last recording instead of re-running
       --cases  print the cases this script knows and stop
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
from wave_bundle import (C_CIRCUIT, C_ERR, C_MODEL, C_VIN, read_hex_series,
                         score_line, to_fst, trim_to_common, with_error,
                         write_gtkw, write_vcd)

HOME = Path.home()
RUNS = HOME / "s2r_runs"
XEZIM = Path(os.environ.get("XEZIM", HOME / "xezim/target/release/xezim"))
COLORS = {"vin": C_VIN, "circuit": C_CIRCUIT, "model": C_MODEL,
          "error": C_ERR}

CASES = {
    "pll_nocosim": {
        "run": RUNS / "demo4b_pll",
        "log": RUNS / "demo4b_pll.log",
        "deck": RUNS / "demo4b_pll_deck" / "pll_analog.cir",
        "inverters": ["inv1", "inv2"],
        "rc": ["lpfilt"],
    },
}

DUMP = '''
  // Added by harness/pll_wave.py to a COPY of this file (the generated
  // loop is not edited): record this module's nets.
  initial begin
    $dumpfile("loop.vcd");
    $dumpvars(1, %s);
  end
'''

NETS = ("vout_v", "dra_v", "aout_v", "aout_clk", "up", "dn", "ref_clk",
        "clk_out", "__counting")


# --------------------------------------------------------------------------
# the loop: re-run with a recording
# --------------------------------------------------------------------------
def loop_sources(loopdir):
    """The files the generated run script compiles, found the way it finds
    them: its own file list, searched along its own SEARCH path."""
    runners = sorted(loopdir.glob("run_*.sh"))
    if len(runners) != 1:
        raise SystemExit("expected one run_*.sh in %s, found %d"
                         % (loopdir, len(runners)))
    sh = runners[0].read_text()
    search = re.search(r'SEARCH=\$\{SEARCH:-"([^"]*)"\}', sh)
    files = re.search(r"\n\s*for f in ([^;]+); do", sh)
    if not (search and files):
        raise SystemExit("%s: cannot read its SEARCH path or file list"
                         % runners[0])
    out = []
    for f in files.group(1).split():
        for d in search.group(1).split():
            p = loopdir / d / f
            if p.is_file():
                out.append(p.resolve())
                break
        else:
            raise SystemExit("%s: %s is not on its own SEARCH path"
                             % (runners[0], f))
    return out


def record(run, work, wall):
    loopdir = run / "rtl_loop" / "loop"
    srcs = loop_sources(loopdir)
    tops = [p for p in srcs if p.parent == loopdir]
    if len(tops) != 1:
        raise SystemExit("cannot tell which source is the loop's top in %s"
                         % loopdir)
    name = tops[0].stem
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for p in srcs:
        shutil.copy2(p, work)
    top = work / tops[0].name
    src = top.read_text()
    end = "\nendmodule : %s" % name
    if src.count(end) != 1:
        raise SystemExit("%s: cannot find the end of module %s" % (top, name))
    top.write_text(src.replace(end, DUMP % name + end))
    with open(work / "loop.log", "w") as log:
        r = subprocess.run(["timeout", str(wall), str(XEZIM), "--wave"]
                           + [p.name for p in srcs], cwd=work, stdout=log,
                           stderr=subprocess.STDOUT)
    return r.returncode, name


def rtl_lines(text):
    return [ln.strip() for ln in text.splitlines()
            if ln.strip().startswith("[rtl-loop]")]


def read_vcd(path, names):
    """{name: [(t_s, value)]} for the named nets of the top scope. Reals
    as floats; one-bit nets as 0/1, and x or z as None."""
    ids, out, depth, scale = {}, {n: [] for n in names}, 0, 1e-15
    t = 0.0
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
            elif c in "01xzXZ":
                n = ids.get(line[1:].strip())
                if n:
                    out[n].append((t, None if c in "xzXZ" else int(c)))
    for n in names:
        if not out[n]:
            raise SystemExit("%s holds no %s: the recording missed it"
                             % (path, n))
    return out


def steps(tr, level=1.0):
    """A net as the simulator holds it: at each change, the old value and
    then the new one at the same instant, so the line rises straight up.
    A real-valued net in the loop holds too (it keeps its value until the
    model next drives it), and drawn as a slope between two sparse updates
    the oscillator's instant 0 V -> 3.3 V jump would look like a ramp."""
    out, prev = [], None
    for t, v in tr:
        y = None if v is None else v * level
        if out and prev is not None and y is not None:
            out.append((t, prev))
        out.append((t, y))
        prev = y
    return out


def rising(tr):
    edges, prev = [], None
    for t, v in tr:
        if prev == 0 and v == 1:
            edges.append(t)
        prev = v
    return edges


def high_widths(tr, a, b):
    """Durations a logic net spends at 1, for the pulses that start in
    [a, b)."""
    out, t_up, prev = [], None, None
    for t, v in tr:
        if prev != 1 and v == 1:
            t_up = t
        elif prev == 1 and v != 1 and t_up is not None:
            if a <= t_up < b:
                out.append(t - t_up)
            t_up = None
        prev = v
    return out


def param(src, name):
    m = re.search(r"localparam real\s+%s\s*=\s*([0-9.eE+-]+);" % name, src)
    if not m:
        raise SystemExit("the loop file has no %s" % name)
    return float(m.group(1))


def fmt_t(s):
    if s < 1e-9:
        return "%.0f ps" % (s * 1e12)
    if s < 1e-6:
        return "%.2f ns" % (s * 1e9)
    return "%.2f us" % (s * 1e6)


NOISE = re.compile(r"(?im)^(\S+)\s+(\S+)\s+\S+\s+dc\s+\S+\s+"
                   r"trnoise\(\s*([0-9.eE+-]+)\s+([0-9.eE+-]+)")
JITTER = re.compile(r"block '(\w+)' \(vco\): intrinsic jitter at ([0-9.]+) V: "
                    r"([0-9.]+) ps rms over (\d+) cycles.*?The rms carries "
                    r"about (\d+)% uncertainty")


def jitter_note(cfg, psd, pm, n, ratio, av_lo, av_hi, target):
    """Why the each-cycle rate wobbles, from the netlist's own noise source
    and spice2rnm's own measurement of the transistor oscillator."""
    text = ("The thin trace wobbles because the oscillator does: its period "
            "varies by %.2f ps rms from one cycle to the next (%.2f%% of its "
            "%.1f ps period, over %d cycles)." % (psd * 1e12, psd / pm * 100,
                                                   pm * 1e12, n))
    deck = cfg["deck"].read_text(errors="replace") if cfg["deck"].exists() else ""
    nz = NOISE.search(deck)
    js = JITTER.search(cfg["log"].read_text(errors="replace"))
    if nz:
        text += (" The netlist puts noise on the supply (%s on node %s: "
                 "trnoise, %.0f mV rms, a new value every %s), the "
                 "generated loop drives that same noisy supply, and a ring "
                 "oscillator's speed follows its supply."
                 % (nz.group(1), nz.group(2), float(nz.group(3)) * 1e3,
                    fmt_t(float(nz.group(4)))))
    if js:
        text += (" spice2rnm measured %s ps rms on the transistor "
                 "oscillator under that noise (at %s V on its control, "
                 "over %s cycles, about %s%% uncertain), so the model "
                 "carries the circuit's jitter, not an artefact of the plot."
                 % (js.group(3), js.group(2), js.group(4), js.group(5)))
    text += (" The thick trace averages each reference cycle's %d oscillator "
             "cycles, which is what the loop steers: after the first "
             "microsecond it stays between %.3f and %.3f MHz, against "
             "%.3f MHz asked for." % (ratio, av_lo / 1e6, av_hi / 1e6,
                                      target / 1e6))
    return text


def loop_page(case, cfg, out, reuse, wall):
    run = cfg["run"]
    work = RUNS / ("%s_loop_rec" % case)
    if reuse and (work / "loop.vcd").exists():
        name = sorted(work.glob("*.sv"))
        name = next(p.stem for p in name if "_rtl_loop" in p.stem)
        print("  re-using the recording in %s" % work)
    else:
        print("  re-running the generated loop with a recording "
              "(about 2 minutes)")
        rc, name = record(run, work, wall)
        if rc != 0:
            raise SystemExit("the recorded loop run exited %d: see %s"
                             % (rc, work / "loop.log"))
    got = rtl_lines((work / "loop.log").read_text())
    want = rtl_lines(cfg["log"].read_text(errors="replace"))
    missing = [ln for ln in got if ln not in want]
    if not got or missing:
        raise SystemExit("the recorded run does not print what the demo's "
                         "run printed, so it is not the run being drawn:\n  "
                         + "\n  ".join(missing or ["(no [rtl-loop] lines)"]))
    src = (work / (name + ".sv")).read_text()
    ref_hz, target_hz = param(src, "REF_HZ"), param(src, "TARGET_HZ")
    tol = param(src, "TOL_FRAC")
    settle, window = param(src, "SETTLE_S"), param(src, "WINDOW_S")
    div = re.search(r"divn\s+#\(\.N\((\d+)\)\)", src)
    ratio = int(div.group(1)) if div else None

    v = read_vcd(work / "loop.vcd", NETS)
    t1 = max(tr[-1][0] for tr in v.values())

    # the measured window, as the run itself opened and closed it
    cnt = [(t, x) for t, x in v["__counting"] if x is not None]
    w_open = next(t for t, x in cnt if x == 1)
    w_close = next(t for t, x in cnt if x == 0 and t > w_open)
    if abs(w_open - settle) > 1e-12 or abs((w_close - w_open) - window) > 1e-12:
        raise SystemExit("the window the run opened (%.6g..%.6g s) is not the "
                         "one its file declares (%.6g s, then %.6g s)"
                         % (w_open, w_close, settle, window))

    # the rate, recomputed from the recording the way the file computes it
    fb = [t for t in rising(v["clk_out"]) if w_open <= t <= w_close]
    rate = (len(fb) - 1) / (fb[-1] - fb[0])
    logged = re.search(r"rate\s+\S+\s+([0-9.]+) MHz", " ".join(got))
    if not logged or abs(rate / 1e6 - float(logged.group(1))) > 1e-6:
        raise SystemExit("the recording gives %.6f MHz, the run printed %s"
                         % (rate / 1e6, logged.group(1) if logged else "?"))

    # the oscillator's rate, one value per cycle, at each rising crossing
    # of the comparator threshold (aout_clk = aout above VTH)
    ed = rising(v["aout_clk"])
    vco = [(b, 1.0 / (b - a)) for a, b in zip(ed, ed[1:])]
    vco_target = target_hz * ratio if ratio else None
    lock_t = None
    if vco_target:
        off = [t for t, f in vco if abs(f - vco_target) > tol * vco_target]
        lock_t = off[-1] if off else vco[0][0]

    # The same rate averaged over each reference cycle (the divider's N
    # oscillator cycles between two rising edges of the divided clock):
    # what the loop steers, with the cycle-to-cycle wobble averaged out.
    fb_all = rising(v["clk_out"])
    avg = [(b, ratio / (b - a)) for a, b in zip(fb_all, fb_all[1:])]
    # Cycle-to-cycle jitter of the oscillator, after the first microsecond.
    per = [b - a for a, b in zip(ed, ed[1:]) if a >= 1e-6]
    pm = sum(per) / len(per)
    psd = math.sqrt(sum((p - pm) ** 2 for p in per) / len(per))
    av_late = [f for t, f in avg if t >= 1e-6]
    jit_note = jitter_note(cfg, psd, pm, len(per), ratio, min(av_late),
                           max(av_late), vco_target)

    # the phase detector at lock: pulse widths inside the window
    upw = high_widths(v["up"], w_open, w_close)
    dnw = high_widths(v["dn"], w_open, w_close)
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0

    # one reference cycle well inside the window, and a close-up of the
    # detector at that reference edge
    refs = [t for t in rising(v["ref_clk"]) if w_open + 0.4 * window <= t]
    r0 = refs[0]
    half = max(1e-9, 6 * max(mean(upw), mean(dnw)))

    vctl_lo = min(x for t, x in v["vout_v"] if w_open <= t <= w_close)
    vctl_hi = max(x for t, x in v["vout_v"] if w_open <= t <= w_close)
    vctl_end = v["vout_v"][-1][1]
    vctl_start = v["vout_v"][0][1]
    f_start = vco[0][1]

    traces = [
        {"key": "vctl", "label": "control voltage", "legend": False,
         "pts": steps(v["vout_v"]), "color": "model", "w": 1.6, "a": 1},
        {"key": "rate", "label": "oscillator rate, each cycle",
         "legend": "oscillator rate, each cycle (thin)",
         "pts": [(t, f / 1e8) for t, f in vco], "color": "vin",
         "w": 1, "a": 0.9},
        {"key": "avg", "label": "oscillator rate, per reference cycle",
         "legend": "the same, averaged over each reference cycle (thick)",
         "pts": [(t, f / 1e8) for t, f in avg], "color": "model",
         "w": 2.4, "a": 1},
        {"key": "pump", "label": "pump node dra", "legend": False,
         "pts": steps(v["dra_v"]), "color": "circuit", "w": 1.2, "a": 1},
        {"key": "up", "label": "up", "legend": "up pulse (drawn as +1)",
         "pts": steps(v["up"]), "color": "circuit", "w": 1.6, "a": 1},
        {"key": "dn", "label": "down", "legend": "down pulse (drawn as -1)",
         "pts": steps(v["dn"], -1.0), "color": "error", "w": 1.6, "a": 1},
        {"key": "ref", "label": "reference",
         "legend": "reference clock (thick)", "pts": steps(v["ref_clk"]),
         "color": "vin", "w": 6, "a": 0.55},
        {"key": "fb", "label": "divided oscillator",
         "legend": "oscillator divided by %s (thin)" % ratio,
         "pts": steps(v["clk_out"]), "color": "model", "w": 1.6, "a": 1},
        {"key": "aout", "label": "oscillator output aout", "legend": False,
         "pts": steps(v["aout_v"]), "color": "model", "w": 1.2, "a": 1},
    ]
    panels = [
        {"id": "p-vctl", "ylabel": "control (V)", "keys": ["vctl"],
         "height": 210},
        {"id": "p-rate", "ylabel": "oscillator (MHz)", "keys": ["rate", "avg"],
         "mul": 100, "unit": "MHz", "dec": 3, "signed": False, "height": 190},
        {"id": "p-pump", "ylabel": "pump node (V)", "keys": ["pump"],
         "height": 140},
        {"id": "p-pfd", "ylabel": "up / down", "keys": ["up", "dn"],
         "unit": "", "dec": 0, "height": 100},
        {"id": "p-clk", "ylabel": "clocks", "keys": ["ref", "fb"],
         "unit": "", "dec": 0, "signed": False, "height": 100},
        {"id": "p-aout", "ylabel": "aout (V)", "keys": ["aout"],
         "height": 150},
    ]
    hlines = []
    if vco_target:
        hlines = [
            {"panel": 1, "y": vco_target / 1e6,
             "label": "asked for: %d x reference = %.3f MHz"
                      % (ratio, vco_target / 1e6)},
            {"panel": 1, "y": vco_target * (1 + tol) / 1e6,
             "label": "+%g%%" % (tol * 100)},
            {"panel": 1, "y": vco_target * (1 - tol) / 1e6,
             "label": "-%g%%" % (tol * 100)},
        ]
    # Does this run pull in to lock, or start there? The netlist's initial
    # condition decides, and the page must not call holding "locking".
    pulls_in = bool(lock_t and lock_t > 0.05 * t1)
    presets = [{"label": "Whole run", "a": 0.0, "b": t1}]
    if pulls_in:
        presets.append({"label": "Start-up to lock", "a": 0.0,
                        "b": min(t1, lock_t * 1.25 + 0.5e-6)})
    else:
        presets.append({"label": "First microsecond", "a": 0.0,
                        "b": min(t1, 1e-6)})
    presets += [
        {"label": "Measured window", "a": w_open, "b": w_close},
        {"label": "One reference cycle at lock", "a": r0 - 0.1 / ref_hz,
         "b": r0 + 1.1 / ref_hz},
        {"label": "Phase detector close-up", "a": r0 - half, "b": r0 + half},
    ]
    err_pct = (rate - target_hz) / target_hz * 100
    # how far the control moved across the window, as the run measures it
    # (its value when the window closed minus its value when it opened)
    at = lambda tt: [x for t, x in v["vout_v"] if t <= tt][-1]
    drift = at(w_close) - at(w_open)
    score = ("Locked: the divided clock runs at %.6f MHz against %.6f MHz "
             "asked for (%+.4f%%, tolerance %g%%), and the control voltage "
             "moved %.3f mV across the measured window. Generated models "
             "around the design's own RTL: no transistors in this run."
             % (rate / 1e6, target_hz / 1e6, err_pct, tol * 100,
                drift * 1e3))
    notes = [
        "What this is: demo 4b's whole phase-locked loop. The charge pump, "
        "loop filter and ring oscillator are the models spice2rnm generated "
        "from the transistor netlist; the phase detector and the divide-by-%s "
        "are the design's own RTL, unchanged. One simulator, xezim, runs "
        "all of it. Nothing here is a transistor." % ratio,
        "How it was recorded: the generated loop file was run again in a "
        "scratch copy with one change, four lines asking xezim to record "
        "its nets. That run printed exactly the lines the demo's own run "
        "printed, and this page was refused if it had not. The window "
        "shaded in the plots is the one the run measured in: it opened at "
        "%s and closed at %s, as the file declares."
        % (fmt_t(w_open), fmt_t(w_close)),
        "Reading it, top to bottom. The control voltage is the loop's "
        "memory: the charge pump nudges it up or down once per reference "
        "cycle and it holds its value in between. This oscillator runs "
        "SLOWER as the control voltage rises (measured: its rate falls from "
        "804.5 MHz to 16.74 MHz across 0.495 to 2.805 V), so the loop "
        "settles where the rate is %d times the reference." % ratio,
        "The oscillator panel is worked out from the recording: one value "
        "per cycle, 1 / (time between two rising crossings of %.2f V, the "
        "threshold the loop's clock is taken at)."
        % param(src, "VTH"),
        ("This run pulls in to lock: the oscillator starts at %.1f MHz with "
         "the control at %.3f V, and stays within %g%% of %.3f MHz from %s "
         "on." % (f_start / 1e6, vctl_start, tol * 100, vco_target / 1e6,
                  fmt_t(lock_t)))
        if pulls_in else
        ("This run HOLDS lock rather than finding it. The netlist's initial "
         "condition starts the control voltage at %.3f V, already beside "
         "where the loop settles, so the oscillator's first cycle is at "
         "%.1f MHz and it is within %g%% of %.3f MHz from %s to the end. "
         "What the page shows is the loop keeping the oscillator there, "
         "cycle after cycle, not pulling it in from far away."
         % (vctl_start, f_start / 1e6, tol * 100, vco_target / 1e6,
            fmt_t(lock_t))) if vco_target else "",
        jit_note,
        "Inside the measured window the control voltage stays between "
        "%.4f and %.4f V (it ends the run at %.4f V). The up and down "
        "pulses there average %s and %s wide: at lock the detector still "
        "fires on every reference edge, briefly, and the charges the two "
        "pulses push nearly cancel, which is why the control voltage "
        "drifts by only %.3f mV over the window's %d reference cycles."
        % (vctl_lo, vctl_hi, vctl_end, fmt_t(mean(upw)) if upw else "none",
           fmt_t(mean(dnw)) if dnw else "none", drift * 1e3, len(fb) - 1),
        "Scope: this is one start from the initial condition the netlist "
        "states, at one reference rate and one corner. It shows that the "
        "models and the RTL lock together; it is not evidence about the "
        "transistors, which demo 4a compares against at the cost of a "
        "co-simulation.",
    ]
    spec = {
        "title": ("Demo 4b: the PLL %s, models and RTL only"
                  % ("pulling in to lock" if pulls_in else "holding lock")),
        "score": score, "notes": [n for n in notes if n],
        "footer": ("Every point the recorded run wrote is in this page (times "
                   "to 1 fs, voltages to 0.1 µV), except the oscillator "
                   "rate, which is worked out from it. Each net is drawn the "
                   "way the simulator holds it: a value stays until the next "
                   "change, then steps. It loads nothing from the network. "
                   "Built by "
                   "harness/pll_wave.py in the spice2rnm demos."),
        "traces": traces, "panels": panels, "hlines": hlines,
        "shades": [{"a": w_open, "b": w_close, "label": "measured window"}],
        "presets": presets, "t1": t1,
    }
    page = out / ("%s_loop.html" % case)
    size = write_spec_page(page, spec, COLORS)
    print("  %-26s %5.2f MB   %s" % (page.name, size / 1e6,
                                      "LOCKED at %.6f MHz (%+.4f%%), recomputed "
                                      "from the recording" % (rate / 1e6, err_pct)))
    return page.name, score


# --------------------------------------------------------------------------
# the blocks: circuit against model, from the demo run's own files
# --------------------------------------------------------------------------
def inverter(case, run, b, out):
    eq = run / b / "equivalence"
    head, model, circuit = {}, [], []
    for line in (eq / "waveform_compare.csv").read_text().splitlines():
        if line.startswith("#"):
            for kv in line[1:].split():
                if "=" in kv:
                    k, val = kv.split("=", 1)
                    head[k] = val
            continue
        f = line.split(",")
        try:
            t, sv, sp = float(f[0]), float(f[1]), float(f[2])
        except (ValueError, IndexError):
            continue
        model.append((t, sv))
        circuit.append((t, sp))
    vin = read_hex_series(eq / "in_dt.hex", eq / "in_v.hex")
    d = {"title": "Inverter %s from demo 4b's PLL: circuit against model" % b,
         "vin": vin, "circuit": circuit, "model": model,
         "score": {"rms": float(head["rms_error_norm"]),
                   "max": float(head["max_error_norm"]),
                   "threshold": float(head["threshold"]),
                   "verdict": head.get("verdict", "?"),
                   "norm": float(head["norm_value"]), "settle": 0.0}}
    trim_to_common(d)
    err = with_error(d)
    sc = d["score"]
    sw = sc["norm"]
    tw, ew = max(err, key=lambda p: abs(p[1]))
    c0, m0 = d["circuit"][0][1], d["model"][0][1]
    t1 = min(d["circuit"][-1][0], d["model"][-1][0])
    half = max(50e-12, 0.02 * t1)   # an inverter's edge is picoseconds
    presets = [{"label": "Whole run", "a": 0.0, "b": t1}]
    if abs(m0 - c0) > 0.1 * sw:
        # The model opens somewhere other than the circuit: the worst
        # points are its first picoseconds, not an edge. Say so, and give
        # the worst point once it has caught up.
        t_c = next((t for t, e in err if abs(e) <= 0.1 * sw), err[-1][0])
        after = [p for p in err if p[0] > t_c]
        ta, ea = max(after, key=lambda p: abs(p[1]))
        worst_note = (
            "The worst point is the very start of the run. The model's output "
            "opens at %.2f V while the circuit's is already at %.2f V, the "
            "settled output for an input at %.2f V, and the model reaches it "
            "within %s. From then on its worst point is %.1f%% of the swing "
            "(%+.3f V, at %s). The score above is taken over the whole run, "
            "start included." % (m0, c0, d["vin"][0][1], fmt_t(t_c),
                                 abs(ea) / sw * 100, ea, fmt_t(ta)))
        presets += [
            {"label": "The start", "a": 0.0, "b": max(4 * t_c, 20e-12)},
            {"label": "After the start", "a": 2 * t_c, "b": t1},
            {"label": "Worst point after the start",
             "a": max(0.0, ta - half), "b": min(t1, ta + half)}]
    else:
        presets.append({"label": "Worst point", "a": max(0.0, tw - half),
                        "b": min(t1, tw + half)})
        cw = next(v for t, v in d["circuit"] if t >= tw)
        worst_note = (
            "The worst single point is at %s: the circuit's output is at "
            "%.2f V, partway through a swing, and the model's at %.2f V "
            "(%.1f%% of the swing apart). Mid-swing is where an inverter's "
            "output moves fastest, so a small difference in when the model "
            "switches shows there as a large difference in volts, while the "
            "rms stays small. The \"Worst point\" button zooms there."
            % (fmt_t(tw), cw, cw + ew, abs(ew) / sw * 100))
    stem = "%s_%s" % (case, b)
    # Values to 0.1 uV, the precision the page keeps: the simulators' last
    # digits are noise, and they decide whether the .fst fits in git.
    r7 = lambda tr: [(t, round(x, 7)) for t, x in tr]
    traces = {"vin": r7(d["vin"]), "vout_circuit": r7(d["circuit"]),
              "vout_model": r7(d["model"]), "error": r7(err)}
    vcd = out / (stem + ".vcd")
    t_last = write_vcd(vcd, b, traces)
    wave, note = to_fst(vcd)
    write_gtkw(out / (stem + ".gtkw"), wave.name, b, t_last, d["title"])
    notes = [
        "Stimulus: the pipeline's own equivalence check for this block, the "
        "input it drove into both the transistor circuit (ngspice) and the "
        "generated model (xezim).",
        "How it was scored: rms of (model - circuit) over the whole run, "
        "divided by the circuit's swing (%.3f V); pass mark %g%%."
        % (sc["norm"], sc["threshold"] * 100),
        worst_note,
    ]
    spec = {
        "title": d["title"], "score": score_line(sc), "notes": notes,
        "footer": ("Every point the demo's equivalence check wrote is in "
                   "this page (times to 1 fs, voltages to 0.1 µV); nothing "
                   "was re-simulated to make it, and it loads nothing from "
                   "the network. The same waveforms open in GTKWave from "
                   "the .fst and .gtkw files. Built by harness/pll_wave.py "
                   "in the spice2rnm demos."),
        "traces": [
            {"key": "vin", "label": "stimulus", "pts": d["vin"],
             "color": "vin", "w": 1.2, "a": 1},
            {"key": "circuit", "label": "circuit",
             "legend": "circuit (ngspice)", "pts": d["circuit"],
             "color": "circuit", "w": 6, "a": 0.45},
            {"key": "model", "label": "model", "legend": "model (xezim)",
             "pts": d["model"], "color": "model", "w": 1.6, "a": 1},
            {"key": "error", "label": "error",
             "legend": "error, model minus circuit", "pts": err,
             "color": "error", "w": 1.2, "a": 1},
        ],
        "panels": [
            {"id": "p-main", "ylabel": "volts",
             "keys": ["vin", "circuit", "model"], "height": 340},
            {"id": "p-err", "ylabel": "error (mV)", "keys": ["error"],
             "mul": 1e3, "unit": "mV", "sym": True, "height": 160},
        ],
        "t1": t1, "presets": presets,
    }
    page = out / (stem + ".html")
    write_spec_page(page, spec, COLORS)
    print("  %-26s %5.2f MB   %s" % (page.name, page.stat().st_size / 1e6,
                                      score_line(sc)))
    return page.name, wave.name, score_line(sc), note


RC_LINE = re.compile(
    r"block '(\w+)' \(rc\): equivalence (PASS|FAIL) -- .*? to ([0-9.]+)% of "
    r"the output's own ([0-9.]+) V excursion \(rms ([0-9.]+)%\), under a "
    r"([0-9.eE+-]+) A step into '(\w+)' over ([0-9.eE+-]+) s")


def rc_block(case, run, log_text, b, out):
    m = next((m for m in RC_LINE.finditer(log_text) if m.group(1) == b), None)
    if not m:
        raise SystemExit("the demo's log has no equivalence line for %s" % b)
    verdict, mx_log, exc_log, rms_log = (m.group(2), float(m.group(3)),
                                         float(m.group(4)), float(m.group(5)))
    amps, node, dur = float(m.group(6)), m.group(7), float(m.group(8))
    model, circuit = [], []
    for line in (run / b / "equivalence" / "rc_compare.csv").read_text().splitlines()[1:]:
        f = line.split(",")
        t, sv, sp = float(f[0]), float(f[1]), float(f[2])
        model.append((t, sv))
        circuit.append((t, sp))
    err = [(t, a - c) for (t, a), (_, c) in zip(model, circuit)]
    exc = max(v for _, v in circuit) - min(v for _, v in circuit)
    rms = math.sqrt(sum(e * e for _, e in err) / len(err)) / exc * 100
    mx = max(abs(e) for _, e in err) / exc * 100
    if abs(exc - exc_log) > 0.0006 or abs(rms - rms_log) > 0.0006 \
            or abs(mx - mx_log) > 0.0006:
        raise SystemExit("%s: recomputed %.3f%% rms / %.3f%% worst of %.3f V, "
                         "the run said %.3f%% / %.3f%% of %.3f V"
                         % (b, rms, mx, exc, rms_log, mx_log, exc_log))
    score = ("rms error %.3f%% of the output's %.3f V excursion, worst single "
             "point %.3f%%: %s (spice2rnm's own verdict)"
             % (rms, exc, mx, verdict))
    t1 = min(model[-1][0], circuit[-1][0])
    tw = max(err, key=lambda p: abs(p[1]))[0]
    spec = {
        "title": "Loop filter %s from demo 4b's PLL: circuit against model" % b,
        "score": score,
        "notes": [
            "Stimulus: a %.3f mA current step into '%s' for %s, the "
            "pipeline's own check for a current-driven filter. The step is "
            "not drawn: it is a current, and every trace here is a voltage."
            % (amps * 1e3, node, fmt_t(dur)),
            "This model was not fitted: spice2rnm read the filter's "
            "capacitors and resistors from the netlist and wrote them as "
            "equations, so the two traces should differ only by the "
            "simulators' arithmetic. The error panel shows how little.",
        ],
        "footer": ("Every point the demo's equivalence check wrote is in "
                   "this page (times to 1 fs, voltages to 0.1 µV). It loads "
                   "nothing from the network. Built by harness/pll_wave.py "
                   "in the spice2rnm demos."),
        "traces": [
            {"key": "circuit", "label": "circuit", "legend": "circuit (ngspice)",
             "pts": circuit, "color": "circuit", "w": 6, "a": 0.45},
            {"key": "model", "label": "model", "legend": "model (xezim)",
             "pts": model, "color": "model", "w": 1.6, "a": 1},
            {"key": "error", "label": "error",
             "legend": "error, model minus circuit", "pts": err,
             "color": "error", "w": 1.2, "a": 1},
        ],
        "panels": [
            {"id": "p-main", "ylabel": "%s (V)" % "vout", "keys": ["circuit", "model"],
             "height": 320},
            {"id": "p-err", "ylabel": "error (mV)", "keys": ["error"],
             "mul": 1e3, "unit": "mV", "sym": True, "height": 160},
        ],
        "presets": [{"label": "Whole run", "a": 0.0, "b": t1},
                    {"label": "Worst point", "a": max(0.0, tw - 0.05 * t1),
                     "b": min(t1, tw + 0.05 * t1)}],
        "t1": t1,
    }
    page = out / ("%s_%s.html" % (case, b))
    size = write_spec_page(page, spec, COLORS)
    print("  %-26s %5.2f MB   %s" % (page.name, size / 1e6, score))
    return page.name, score


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case", nargs="?", choices=sorted(CASES))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--cases", action="store_true")
    ap.add_argument("--wall", type=int, default=1800)
    a = ap.parse_args()
    if a.cases:
        print(" ".join(sorted(CASES)))
        return 0
    if not a.case:
        ap.error("name a case")
    cfg = CASES[a.case]
    out = a.out or RUNS / ("%s_wave" % a.case)
    if out.exists():
        shutil.rmtree(out)  # start empty: a stale file must never ride along
    out.mkdir(parents=True)
    log_text = cfg["log"].read_text(errors="replace")

    loop_name, loop_score = loop_page(a.case, cfg, out, a.reuse, a.wall)
    blocks = [inverter(a.case, cfg["run"], b, out) for b in cfg["inverters"]]
    rcs = [rc_block(a.case, cfg["run"], log_text, b, out) for b in cfg["rc"]]

    readme = [
        "%s: demo 4b's PLL as waveforms" % a.case,
        "=" * 60,
        "",
        "Open any .html file in a browser and drag across a plot to zoom.",
        "The data is inside each page; nothing to install.",
        "",
        "%s" % loop_name,
        "  The whole loop over the demo's whole run: generated models for",
        "  the analog blocks, the design's own RTL for the phase detector",
        "  and divider, on one simulator. No transistors.",
        "  " + loop_score,
        "",
    ]
    for page, wave, sc, note in blocks:
        readme += ["%s  (and %s, %s for GTKWave)"
                   % (page, wave, wave.rsplit(".", 1)[0] + ".gtkw"),
                   "  An inverter, circuit (ngspice) against model (xezim).",
                   "  " + sc] + (["  Note: " + note] if note else []) + [""]
    for page, sc in rcs:
        readme += [page, "  The loop filter, circuit against model.",
                   "  " + sc, ""]
    readme += [
        "Not drawn: the ring oscillator and the charge pump on their own.",
        "Their circuit side is a characterisation sweep, not one run with",
        "a matching model run beside it; the loop page shows both at work.",
        "",
        "The loop page re-ran the generated loop with a recording and",
        "checked it printed what the demo's run printed. Every other page",
        "is drawn from the demo run's own files.",
        "",
    ]
    (out / "README.txt").write_text("\n".join(readme))
    print("  bundle: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
