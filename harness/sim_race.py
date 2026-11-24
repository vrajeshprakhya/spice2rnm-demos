#!/usr/bin/env python3
"""Race SPICE against the generated model, on the same job, and say how long
each took.

The speed-up is the reason a model exists, so it is measured here every time
the showcase is refreshed instead of being quoted from an old run. Each race
uses a pair the equivalence check already left behind in the run directory:

  * the transistor circuit as an ngspice deck, and
  * the generated model with the testbench that drives it with the SAME
    input, over the same stretch of simulated time,

so both sides do the same job and only the thing doing the computing
differs. Both are run from a scratch copy, so timing never writes over the
evidence the showcase publishes.

The times are wall clock, start to finish as a user would run them: starting
the program, reading the input, simulating, writing the result. When both
sides finish in under REPEAT_BELOW_S seconds the race is run three times and
the median kept with the spread printed; otherwise once, and it says so.

    python3 harness/sim_race.py CASE [--runs ~/s2r_runs] [--out DIR]

writes DIR/timing.txt (for a reader) and DIR/timing.json (for a tool).
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
NGSPICE = os.environ.get("NGSPICE", str(HOME / "ngspice-install/bin/ngspice"))
XEZIM = os.environ.get("XEZIM", str(HOME / "xezim/target/release/xezim"))
S2R = Path(os.environ.get("S2R", str(HOME / "spice2rnm")))
# THREE RUNS, NOT ONE, below two minutes a side. On this machine the same
# race measured 23 s and then 65 s for SPICE a few minutes apart (and 51 s
# then 93 s for a model), so one run is a sample of the machine as much as
# of the simulators. The two sides take turns inside each run, so a busy
# machine slows both; the median is kept and the spread is printed.
REPEAT_BELOW_S = 120.0
TIMEOUT_S = 3600


# ------------------------------------------------------------------ the pairs
def waveform(label, eqdir):
    """The waveform route: spice_tran/transient.cir against the model run by
    tb_equiv.sv. The model's file is read from the command the check itself
    recorded in xezim.log, so the race runs exactly what was compared."""
    return {"kind": "waveform", "label": label, "dir": eqdir}


def rc(label, blockdir):
    """The RC route: rc_tran.cir against tb_rc.sv driving <block>.sv."""
    return {"kind": "rc", "label": label, "dir": blockdir}


CASES = {
    "lpf2": {"run": "lpf2",
             "pairs": [waveform("RC low-pass filter (rc_lpf2)", "equivalence")]},
    "dcc2": {"run": "dcc2",
             "pairs": [waveform("duty-cycle corrector (dcc)", "equivalence")],
             # Printed only while the model is the slower side, so it
             # cannot outlive the problem it explains.
             "slow_why": (
                 "two causes, both in the model rather than the circuit. It "
                 "takes a fixed 1.76 ps step for the whole run, about "
                 "290,000 steps, where ngspice stretches its step whenever "
                 "the signal is quiet. And its $tanh switching curve sits "
                 "inside the step loop, which keeps xezim in its slower "
                 "interpreted mode (its log shows about 150 us per step)")},
    "pi": {"run": "demo3_pi",
           "pairs": [{"kind": "pi", "label": "phase interpolator, all 9 codes"}]},
    "pll_cosim": {
        "run": "demo4_pll",
        "pairs": [waveform("inverter inv1", "inv1/equivalence"),
                  waveform("inverter inv2", "inv2/equivalence"),
                  rc("loop filter lpfilt", "lpfilt")],
        "system": True,
        "not_raced": {
            "ro_vco": "oscillator: its SPICE side is the characterisation "
                      "sweep, not a deck kept beside the model's run",
            "cpump": "charge pump: the same, its SPICE side is the "
                     "characterisation sweep"}},
    "pll_nocosim": {
        "run": "demo4b_pll",
        "pairs": [waveform("inverter inv1", "inv1/equivalence"),
                  waveform("inverter inv2", "inv2/equivalence"),
                  rc("loop filter lpfilt", "lpfilt")],
        "not_raced": {
            "ro_vco": "oscillator: its SPICE side is the characterisation "
                      "sweep, not a deck kept beside the model's run",
            "cpump": "charge pump: the same"}},
}

NOT_RACED_CASES = {
    "ctle_sparams": (
        "Not raced. SPICE answers this question in the frequency domain, one "
        "small-signal solve per frequency, while the model has to be run in "
        "time until each tone settles. The two are different calculations, "
        "so a ratio of their run times would not mean 'the model is N times "
        "faster' at anything a user would do."),
    "lpf2_house": (
        "Not raced separately: the same circuit and the same model as lpf2, "
        "generated in the house style. See ../lpf2/timing.txt."),
}


# ------------------------------------------------------------------ helpers
def local_outputs(text):
    """Point every file a deck or testbench WRITES at the current directory,
    so the scratch copy writes into itself and not into the run directory."""
    text = re.sub(r"(?m)^(\s*wrdata\s+)\S*/(\S+)", r"\1\2", text)
    text = re.sub(r'(\$fopen\(\s*")[^"]*/([^"/]+")', r"\1\2", text)
    return text


def copy_rewritten(src, dst):
    dst.write_text(local_outputs(src.read_text()))


def spice_stop_s(deck_text):
    m = re.search(r"(?im)^\s*\.?tran\s+(\S+)\s+(\S+)", deck_text)
    return float(m.group(2)) if m else None


def model_stop_s(stdout, tb_text):
    m = re.search(r"Simulation finished at time (\d+)", stdout)
    u = re.search(r"`timescale\s+(\d+)\s*(fs|ps|ns|us|ms|s)\b", tb_text)
    if not m or not u:
        return None
    scale = {"fs": 1e-15, "ps": 1e-12, "ns": 1e-9, "us": 1e-6, "ms": 1e-3,
             "s": 1.0}[u.group(2)] * int(u.group(1))
    return int(m.group(1)) * scale


def run(cmd, cwd):
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       timeout=TIMEOUT_S)
    return time.perf_counter() - t0, p


def fmt_s(s):
    if s is None:
        return "-"
    return "%.3g s" % s if s < 100 else "%.0f s" % s


def fmt_t(s):
    if s is None:
        return "?"
    for unit, k in (("s", 1), ("ms", 1e-3), ("us", 1e-6), ("ns", 1e-9),
                    ("ps", 1e-12)):
        if s >= k:
            return "%.4g %s" % (s / k, unit)
    return "%.3g s" % s


def git_rev(path):
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short",
                               "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


# ------------------------------------------------------------------ one race
def prepare(pair, rundir, tmp):
    """Copy one pair into tmp. Returns (spice_jobs, model_job, notes):
    spice_jobs is a list of (cwd, deck-name, stop_s); model_job is
    (cwd, [files], tb_text)."""
    kind = pair["kind"]
    if kind == "waveform":
        eq = rundir / pair["dir"]
        log = (eq / "xezim.log").read_text()
        m = re.search(r"^# command\s*:\s*(.+)$", log, re.M)
        files = m.group(1).split()[1:]
        model = Path(files[0])
        tb = eq / "tb_equiv.sv"
        for f in eq.glob("*.hex"):
            shutil.copy(f, tmp / f.name)
        shutil.copy(model, tmp / model.name)
        copy_rewritten(tb, tmp / tb.name)
        sp = tmp / "spice"
        sp.mkdir()
        deck = eq / "spice_tran" / "transient.cir"
        copy_rewritten(deck, sp / deck.name)
        return ([(sp, deck.name, spice_stop_s(deck.read_text()))],
                (tmp, [model.name, tb.name], tb.read_text()))
    if kind == "rc":
        blk = rundir / pair["dir"]
        eq = blk / "equivalence"
        model = blk / (blk.name + ".sv")
        shutil.copy(model, tmp / model.name)
        copy_rewritten(eq / "tb_rc.sv", tmp / "tb_rc.sv")
        sp = tmp / "spice"
        sp.mkdir()
        copy_rewritten(eq / "rc_tran.cir", sp / "rc_tran.cir")
        return ([(sp, "rc_tran.cir",
                  spice_stop_s((eq / "rc_tran.cir").read_text()))],
                (tmp, [model.name, "tb_rc.sv"],
                 (eq / "tb_rc.sv").read_text()))
    if kind == "pi":
        jobs = []
        for d in sorted((rundir / "code_sweep").glob("code*"),
                        key=lambda p: int(p.name[4:])):
            dd = tmp / "spice" / d.name
            dd.mkdir(parents=True)
            copy_rewritten(d / "code.cir", dd / "code.cir")
            jobs.append((dd, "code.cir",
                         spice_stop_s((d / "code.cir").read_text())))
        tb = rundir / "equivalence" / "tb_phase_equiv.sv"
        model = rundir / "pi_therm_rnm.sv"
        shutil.copy(model, tmp / model.name)
        copy_rewritten(tb, tmp / tb.name)
        return jobs, (tmp, [model.name, tb.name], tb.read_text())
    raise ValueError(kind)


def race_once(spice_jobs, model_job):
    t_sp, problems = 0.0, []
    for cwd, deck, _stop in spice_jobs:
        dt, p = run([NGSPICE, "-b", deck], cwd)
        t_sp += dt
        if p.returncode != 0:
            problems.append("ngspice exit %d on %s" % (p.returncode, deck))
        wrote = [f for f in Path(cwd).iterdir()
                 if f.suffix == ".txt" and f.stat().st_size > 0]
        if not wrote:
            problems.append("ngspice wrote no result for %s" % deck)
    cwd, files, tb_text = model_job
    t_m, p = run([XEZIM] + files, cwd)
    if p.returncode != 0 or "Simulation finished" not in p.stdout:
        problems.append("xezim did not finish (exit %d)" % p.returncode)
    m_stop = model_stop_s(p.stdout, tb_text)
    xz = re.search(r"^git (\S+)", p.stdout, re.M)
    return t_sp, t_m, m_stop, (xz.group(1) if xz else None), problems


def race(pair, rundir, outdir):
    with tempfile.TemporaryDirectory(prefix="sim_race_") as tmp:
        tmp = Path(tmp)
        spice_jobs, model_job = prepare(pair, rundir, tmp)
        # THE MODEL RACED MUST BE THE MODEL PUBLISHED. A run directory can
        # be re-run after its case was curated (the PLL's was, a week
        # later), and a time measured on that newer model would sit beside
        # files it says nothing about. In a full refresh the two are always
        # the same file; after --only on another case they may not be.
        cwd, files, _tb = model_job
        shown = outdir / files[0]
        if shown.is_file() and shown.read_bytes() != (cwd / files[0]).read_bytes():
            return {"label": pair["label"], "spice_runs": len(spice_jobs),
                    "spice_seconds": None, "model_seconds": None,
                    "spice_samples": [], "model_samples": [],
                    "spice_simulated_s": None, "model_simulated_s": None,
                    "xezim_build": None, "speedup": None,
                    "problems": ["the run directory's %s differs from the "
                                 "published one (re-run since this case was "
                                 "curated), so timing it would describe a "
                                 "model not shown here" % files[0]]}
        samples = []
        while True:
            r = race_once(spice_jobs, model_job)
            samples.append(r)
            if r[4]:
                break
            if len(samples) >= 3 or max(r[0], r[1]) >= REPEAT_BELOW_S:
                break
    problems = sorted({p for s in samples for p in s[4]})
    t_sp = statistics.median(s[0] for s in samples)
    t_m = statistics.median(s[1] for s in samples)
    stops = [j[2] for j in spice_jobs]
    sp_stop = sum(stops) if all(s is not None for s in stops) else None
    return {
        "label": pair["label"],
        "spice_runs": len(spice_jobs),
        "spice_seconds": t_sp,
        "model_seconds": t_m,
        "spice_samples": [s[0] for s in samples],
        "model_samples": [s[1] for s in samples],
        "spice_simulated_s": sp_stop,
        "model_simulated_s": samples[-1][2],
        "xezim_build": samples[-1][3],
        "speedup": (t_sp / t_m) if t_m and not problems else None,
        "problems": problems,
    }


# ------------------------------------------------------------------ report
def same_window(r):
    a, b = r["spice_simulated_s"], r["model_simulated_s"]
    return a and b and abs(a - b) <= 0.01 * max(a, b)


def write_report(case, cfg, rows, system, outdir, rundir):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    cpu = "unknown CPU"
    try:
        cpu = re.search(r"model name\s*:\s*(.+)",
                        Path("/proc/cpuinfo").read_text()).group(1).strip()
    except Exception:
        pass
    ng = subprocess.run([NGSPICE, "-v"], capture_output=True, text=True).stdout
    ngv = (re.search(r"(ngspice-\S+)", ng) or [None, "ngspice"])[1]
    finished = "not recorded: no result.json at its top"
    for f in ("result.json", "verdict.txt"):
        if (rundir / f).exists():
            finished = datetime.fromtimestamp(
                (rundir / f).stat().st_mtime, timezone.utc
            ).strftime("%Y-%m-%dT%H:%MZ")
            break
    L = ["SPICE against the model, on the same job: %s" % case, ""]
    L += ["Each row is one race. Both sides get the same input and produce the",
          "same output signal. Only the thing doing the computing differs:",
          "ngspice solving the transistor circuit, or xezim running the",
          "generated model.", ""]
    w = max([len(r["label"]) for r in rows] + [len("what")] +
            ([len(system["label"])] if system else []))
    L.append("  %-*s  %-14s  %-14s  %-22s  %s"
             % (w, "what", "SPICE", "model", "simulated time", "model is"))
    for r in rows:
        if r["problems"]:
            verdict = "NOT TIMED: " + "; ".join(r["problems"])
        elif r["speedup"] >= 1:
            verdict = "%.3gx faster" % r["speedup"]
        else:
            verdict = "%.3gx SLOWER" % (1.0 / r["speedup"])
        if r["problems"]:
            sim = "-"
        elif same_window(r):
            sim = "%s each" % fmt_t(r["model_simulated_s"])
        else:
            sim = "%s / %s" % (fmt_t(r["spice_simulated_s"]),
                               fmt_t(r["model_simulated_s"]))
        L.append("  %-*s  %-14s  %-14s  %-22s  %s"
                 % (w, r["label"], fmt_s(r["spice_seconds"]),
                    fmt_s(r["model_seconds"]), sim, verdict))
    if system:
        L.append("  %-*s  %-14s  %-14s  %-22s  %s"
                 % (w, system["label"], fmt_s(system["golden_seconds"]),
                    fmt_s(system["model_seconds"]), "same testbench",
                    "%.3gx faster" % (system["golden_seconds"]
                                      / system["model_seconds"])))
    L.append("")
    notes = []
    for r in rows:
        if len(r["spice_samples"]) > 1:
            notes.append(
                "%s: over %d runs SPICE took %s to %s and the model %s to %s; "
                "the table shows the median of each."
                % (r["label"], len(r["spice_samples"]),
                   fmt_s(min(r["spice_samples"])),
                   fmt_s(max(r["spice_samples"])),
                   fmt_s(min(r["model_samples"])),
                   fmt_s(max(r["model_samples"]))))
        elif r["spice_samples"]:
            notes.append("%s: one run only, because a side took over %g s; "
                         "expect it to vary between refreshes."
                         % (r["label"], REPEAT_BELOW_S))
        if cfg.get("slow_why") and r["speedup"] and r["speedup"] < 1:
            notes.append("%s: the model is the SLOWER side here, for %s."
                         % (r["label"], cfg["slow_why"]))
        if r["spice_runs"] > 1:
            notes.append(
                "%s: SPICE is %d runs, one per code, timed together; the "
                "model is one run that steps through the same codes. Both "
                "measure the same delays, but the model's bench settles each "
                "code in less simulated time, so this is a ratio per JOB, not "
                "per simulated nanosecond." % (r["label"], r["spice_runs"]))
        elif r["spice_simulated_s"] and not same_window(r):
            notes.append("%s: the two sides simulated different lengths of "
                         "time (shown as SPICE / model), so the ratio is per "
                         "job." % r["label"])
    if system:
        notes.append(
            "%s: recorded by spice2rnm in the run itself, not re-raced here. "
            "Both halves ran the design's own testbench for the same "
            "simulated time, one with the transistors in ngspice and one "
            "with the generated models." % system["label"])
    for name, why in (cfg.get("not_raced") or {}).items():
        notes.append("%s: not raced, %s." % (name, why))
    if notes:
        L += ["Notes:"] + ["  - " + n for n in notes] + [""]
    L += ["How it was measured: wall clock on this machine, start to finish",
          "as a user would run each side (start the program, read the input,",
          "simulate, write the result), the two sides taking turns. Median",
          "of 3 runs when both finish in under %g s, otherwise one run."
          % REPEAT_BELOW_S,
          "Both read the pair the equivalence",
          "check left in the run directory, from a scratch copy.", "",
          "Measured %s on %s, %d threads." % (now, cpu, os.cpu_count() or 0),
          "Run directory %s (finished %s)." % (rundir, finished),
          "Simulators: %s; xezim built as %s (its checkout is at %s)."
          % (ngv,
             next((r["xezim_build"] for r in rows if r["xezim_build"]), "?"),
             git_rev(Path(XEZIM).parent.parent.parent)),
          "The model raced is the one in that run directory; STAMP says",
          "which spice2rnm revision made the run."]
    text = "\n".join(L).replace(str(HOME), "~") + "\n"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "timing.txt").write_text(text)
    js = {"case": case, "measured_utc": now, "cpu": cpu,
          "threads": os.cpu_count(), "ngspice": ngv,
          "run_dir": str(rundir).replace(str(HOME), "~"),
          "run_finished_utc": finished, "races": rows, "system": system,
          "not_raced": cfg.get("not_raced") or {}}
    (outdir / "timing.json").write_text(json.dumps(js, indent=2) + "\n")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case", choices=sorted(set(CASES) | set(NOT_RACED_CASES)))
    ap.add_argument("--runs", default=str(HOME / "s2r_runs"))
    ap.add_argument("--out", required=True, help="directory for timing.txt")
    a = ap.parse_args()
    out = Path(a.out)
    if a.case in NOT_RACED_CASES:
        out.mkdir(parents=True, exist_ok=True)
        text = ("SPICE against the model: %s\n\n%s\n"
                % (a.case, NOT_RACED_CASES[a.case]))
        (out / "timing.txt").write_text(text)
        (out / "timing.json").unlink(missing_ok=True)
        print(text, end="")
        return 0
    cfg = CASES[a.case]
    rundir = Path(a.runs) / cfg["run"]
    if not rundir.is_dir():
        print("sim_race: no run directory %s; nothing timed" % rundir)
        return 0
    rows = []
    for pair in cfg["pairs"]:
        print("  racing %s ..." % pair["label"], flush=True)
        rows.append(race(pair, rundir, out))
    system = None
    if cfg.get("system"):
        # The PUBLISHED record where there is one, for the reason race()
        # checks the model: the run directory may have moved on since.
        rj = out / "result.json"
        if not rj.is_file():
            rj = rundir / "result.json"
        r = json.loads(rj.read_text())["result"]
        c = r.get("cosim_system_equivalence") or {}
        if c.get("model_seconds") and c.get("golden_seconds"):
            system = {"label": "whole PLL, co-simulated",
                      "model_seconds": c["model_seconds"],
                      "golden_seconds": c["golden_seconds"]}
    print(write_report(a.case, cfg, rows, system, out, rundir), end="")
    return 1 if any(r["problems"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
