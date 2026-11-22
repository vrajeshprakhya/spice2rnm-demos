#!/usr/bin/env python3
"""Waveforms a customer can open: the circuit and the model, side by side.

The pipeline's own dumps are written for whoever has to explain a
divergence: every RK4 internal, the full run, hundreds of MB, and real
numbers that GTKWave shows as decimal text until someone right-clicks each
one. A reader who just wants to SEE the model track the circuit needs four
traces, already drawn as curves, in a file small enough to download.

So this reads what a demo run already wrote and builds, per stimulus:

  <case>_<stim>.fst    vin, vout_circuit (ngspice), vout_model (the RNM),
                       error (model minus circuit) -- and nothing else
  <case>_<stim>.gtkw   GTKWave layout: those four, drawn as analog curves
  <case>_<stim>.svg    the same overlay as a picture, for docs and README
  <case>_<stim>.html   the same four traces as a zoomable web page, data
                       inside it, nothing to install (wave_page.py)

plus README.txt saying what each trace is and how the score was taken.
Nothing here re-simulates: every number comes from the run's own files,
so a bundle can never disagree with the run it sits beside.

Standard library only. vcd2fst (shipped with GTKWave) turns the VCD into
FST; without it the bundle keeps the VCD and says so.

usage: wave_bundle.py lpf2 [--out DIR]
"""
import argparse
import math
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from wave_page import write_page

HOME = Path.home()
RUNS = HOME / "s2r_runs"


# --------------------------------------------------------------------------
# traces
# --------------------------------------------------------------------------
def read_pairs(path):
    """Two-column text (time, value), skipping anything that is not."""
    out = []
    for line in Path(path).read_text().splitlines():
        f = line.split()
        if len(f) >= 2:
            try:
                out.append((float(f[0]), float(f[1])))
            except ValueError:
                pass
    return out


def interp(tr, t):
    if t <= tr[0][0]:
        return tr[0][1]
    if t >= tr[-1][0]:
        return tr[-1][1]
    lo, hi = 0, len(tr) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if tr[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    (t0, v0), (t1, v1) = tr[lo], tr[hi]
    return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)


def read_hex_series(dt_path, v_path):
    """The equivalence testbench's stimulus: binary64 bit patterns, the
    delays in fs as increments (a negative one means 'no delay')."""
    dts = [struct.unpack(">d", bytes.fromhex(h.strip()))[0]
           for h in Path(dt_path).read_text().split()]
    vs = [struct.unpack(">d", bytes.fromhex(h.strip()))[0]
          for h in Path(v_path).read_text().split()]
    out, t = [], 0.0
    for dt, v in zip(dts, vs):
        if dt >= 0:
            t += dt * 1e-15
        out.append((t, v))
    return out


def settle_time(rnm):
    """10 time constants of the slower pole, read from the model file: the
    start-up allowance prbs_vcd.py and prbs_sweep2.py score from."""
    src = Path(rnm).read_text()
    pole = float(re.search(r"poles \(Hz\): \[([0-9.eE+-]+)", src).group(1))
    return 10 / (2 * math.pi * pole)


def catch_up_time(err, swing, frac=0.01):
    """When the model's start-up is over: the last moment, early in the run,
    that |model - circuit| is above frac of the circuit's swing."""
    early = [t for t, e in err if abs(e) > frac * swing and t < 2e-6]
    return max(early) if early else 0.0


def lpf2_chirp(run):
    """The pipeline's own equivalence check: a chirp, scored over the
    whole run. waveform_compare.csv is already time-aligned and carries
    the verdict in its header."""
    eq = run / "equivalence"
    csv = eq / "waveform_compare.csv"
    head, model, circuit = {}, [], []
    for line in csv.read_text().splitlines():
        if line.startswith("#"):
            for kv in line[1:].split():
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    head[k] = v
            continue
        f = line.split(",")
        try:
            t, sv, sp = float(f[0]), float(f[1]), float(f[2])
        except (ValueError, IndexError):
            continue
        model.append((t, sv))
        circuit.append((t, sp))
    vin = read_hex_series(eq / "in_dt.hex", eq / "in_v.hex")
    # The same start-up allowance the PRBS score uses: 10 time constants of
    # the slower pole, read from the model the run emitted.
    src = (run / "rc_lpf2_rnm.sv").read_text()
    settle = settle_time(run / "rc_lpf2_rnm.sv")
    # The input range the model was characterised over; static_curve clamps
    # outside it (and says so in its own $warning text).
    rng = re.search(r"\(xin < ([0-9.eE+-]+)\) \? [0-9.eE+-]+ : \(\(xin > "
                    r"([0-9.eE+-]+)\)", src)
    in_range = (float(rng.group(1)), float(rng.group(2))) if rng else None
    return {
        "in_range": in_range,
        "stim": "chirp",
        "title": "Full-range sweep with a chirp on top, through the two-pole RC filter",
        "what": ("the pipeline's own equivalence stimulus: a slow sweep "
                 "from 0 V up to the top of the range and back, with a "
                 "small chirp riding on it (a sine whose frequency slides "
                 "upward through the filter's band), so one run exercises "
                 "the whole input range and the whole band"),
        "vin": vin, "circuit": circuit, "model": model,
        "score": {
            "rms": float(head["rms_error_norm"]),
            "max": float(head["max_error_norm"]),
            "threshold": float(head["threshold"]),
            "verdict": head.get("verdict", "?"),
            "norm": float(head["norm_value"]),
            "how": ("rms of (model - circuit) over the whole run, divided "
                    "by the circuit's swing (%s V), the pipeline's own "
                    "equivalence check" % head["norm_value"]),
            "settle": settle,
        },
        "source": str(csv),
    }


def lpf2_prbs(vdir):
    """demo 1, act 5: binary data the model was NOT fitted from, scored
    the way harness/prbs_vcd.py scores it (after 10 tau, on 4000 points)."""
    circuit = read_pairs(vdir / "spice.txt")
    model = read_pairs(vdir / "model.txt")
    vin = read_pairs(vdir / "stim.txt")
    log = (vdir / "prbs.log").read_text()
    logged = None
    for line in log.splitlines():
        if "points over" in line and "ns" in line:
            # "4000 points over 416..800 ns (10 tau settle), ..."
            span = line.split("points over", 1)[1].split("ns", 1)[0]
            logged = float(span.split("..")[0]) * 1e-9
    if not (circuit and model and vin and logged):
        raise SystemExit("PRBS run incomplete in %s: run demo_1_lpf.sh "
                         "(or harness/prbs_vcd.py) first" % vdir)
    # The exact start prbs_vcd.py scored from (10 tau of the model's slow
    # pole). The log prints it rounded to the ns, and scoring from the
    # rounded value samples a slightly different grid (worst point 2.28%
    # against the demo's 2.30%), so recompute it, and use the log only to
    # confirm that the run and the model belong together.
    settle = settle_time(RUNS / "lpf2" / "rc_lpf2_rnm.sv")
    if abs(settle - logged) > 1e-9:
        raise SystemExit("prbs.log scored from %.0f ns but the model's 10 tau "
                         "is %.1f ns: the run and the model do not match, "
                         "rerun demo_1_lpf.sh" % (logged * 1e9, settle * 1e9))
    t1 = min(circuit[-1][0], model[-1][0])
    grid = [settle + (t1 - settle) * i / 3999 for i in range(4000)]
    df = [interp(model, t) - interp(circuit, t) for t in grid]
    sp = [interp(circuit, t) for t in grid]
    exc = max(sp) - min(sp)
    rms = math.sqrt(sum(x * x for x in df) / len(df)) / exc
    mx = max(abs(x) for x in df) / exc
    return {
        "stim": "prbs",
        "title": "PRBS7 at 160 Mb/s through the two-pole RC filter",
        "what": ("binary data: a PRBS7 bit pattern at 160 Mb/s, which the "
                 "model was NOT fitted from; the filter's slow edges smear "
                 "each bit into the next (inter-symbol interference)"),
        "vin": vin, "circuit": circuit, "model": model,
        "score": {
            "rms": rms, "max": mx, "threshold": 0.15,
            "verdict": "PASS" if rms <= 0.15 else "FAIL",
            "norm": exc,
            "how": ("rms of (model - circuit) on 4000 points from %.0f ns, "
                    "divided by the circuit's swing (%.4f V). Before %.0f ns "
                    "the model is still waking up from rest while ngspice "
                    "starts already settled, so that stretch compares two "
                    "starting points, not two filters, and is not scored"
                    % (settle * 1e9, exc, settle * 1e9)),
            "settle": settle,
        },
        "source": str(vdir),
    }


CASES = {
    "lpf2": lambda: [lpf2_prbs(RUNS / "lpf2_vcd"), lpf2_chirp(RUNS / "lpf2")],
}


def trim_to_common(d):
    """Cut every trace at the time BOTH simulators reached. The PRBS model
    runs 12.5 ns past ngspice's last point, and past it the circuit would
    read as its last value held flat, so the error trace would show a jump
    that is the end of the circuit run, not a disagreement."""
    t1 = min(d["circuit"][-1][0], d["model"][-1][0])
    for k in ("vin", "circuit", "model"):
        d[k] = [p for p in d[k] if p[0] <= t1]


def with_error(d):
    """error = model - circuit, at the model's own sample times."""
    c = d["circuit"]
    return [(t, v - interp(c, t)) for t, v in d["model"]]


# --------------------------------------------------------------------------
# VCD -> FST
# --------------------------------------------------------------------------
SIGNALS = [  # (name, key, one line for README / the GTKWave comment)
    ("vin", "vin", "the stimulus driving the filter input, volts"),
    ("vout_circuit", "circuit", "the circuit's output, solved by ngspice, volts"),
    ("vout_model", "model", "the model's output, simulated by xezim, volts"),
    ("error", "error", "vout_model - vout_circuit, volts"),
]


def write_vcd(path, scope, traces):
    """traces: {name: [(t_seconds, value), ...]}. Time in fs. Inside a run
    of equal values only the first and LAST points are written: a held
    level costs two points, and a viewer that keeps the last one draws a
    flat top and then the edge. (GTKWave does not keep it -- it drops a
    change to the same value -- so the stimulus is drawn as steps there;
    see write_gtkw.)"""
    ids = {n: chr(33 + i) for i, n in enumerate(traces)}
    events = []
    for n, tr in traces.items():
        ss = ["%.9g" % v for _, v in tr]
        for k, (t, _) in enumerate(tr):
            if (k == 0 or k == len(tr) - 1 or ss[k] != ss[k - 1]
                    or ss[k] != ss[k + 1]):
                events.append((int(round(t * 1e15)), ids[n], ss[k]))
    events.sort(key=lambda e: e[0])
    with open(path, "w") as f:
        f.write("$timescale 1fs $end\n$scope module %s $end\n" % scope)
        for n in traces:
            f.write("$var real 64 %s %s $end\n" % (ids[n], n))
        f.write("$upscope $end\n$enddefinitions $end\n")
        now = None
        for t, i, s in events:
            if t != now:
                f.write("#%d\n" % t)
                now = t
            f.write("r%s %s\n" % (s, i))
    return events[-1][0]  # the last timestamp, fs


def to_fst(vcd):
    tool = shutil.which("vcd2fst")
    if not tool:
        return vcd, "vcd2fst not found (it ships with GTKWave): kept the VCD"
    fst = vcd.with_suffix(".fst")
    r = subprocess.run([tool, str(vcd), str(fst)], capture_output=True,
                       text=True)
    if r.returncode != 0 or not fst.exists():
        return vcd, "vcd2fst failed (%s): kept the VCD" % r.stderr.strip()[-200:]
    vcd.unlink()
    return fst, None


# GTKWave trace flags (analyzer.h): signed | right-justify | analog
# interpolated draws a real as a curve; a following @20000 (analog blank
# stretch) line plus '-' rows makes that curve taller. Analog STEP holds
# each value until the next: right for the stimulus, a PWL whose flat tops
# GTKWave would otherwise draw as slopes (it drops a repeated value, so
# interpolation runs straight from one bit's edge to the next one's).
GTKW_ANALOG = "@10420"
GTKW_STEP = "@8420"
GTKW_STRETCH = "@20000"


def gtkw_full_zoom(t_last_fs):
    """The zoom that shows the whole run at [size] 1400 860. GTKWave's zoom
    is a base-2 log of time per pixel, so it moves by log2 of the run
    length. Anchored on GTKWave 3.3.126's own Zoom_Full: -27.075308 for a
    run ending at 812,500,000 fs; this formula then reproduces its value
    for the 7.85 us chirp to 4 decimals. Then 0.6 further out (about 1.5x),
    because the window often opens narrower than [size] asks: on a scaled
    display it opened 1162 px wide and cut the PRBS run off at 620 ns."""
    return -27.075308 - math.log2(t_last_fs / 812500000.0) - 0.6


def write_gtkw(path, wave_name, scope, t_last_fs, title):
    rows = [
        "[*] %s" % title,
        "[*] Open with:  gtkwave %s %s" % (wave_name, Path(path).name),
        '[dumpfile] "%s"' % wave_name,
        "[timestart] 0",
        "[size] 1400 860",
        # zoom to the whole run; then the primary and 26 named markers, unset
        "*%.6f %s" % (gtkw_full_zoom(t_last_fs), " ".join(["-1"] * 27)),
        "[treeopen] %s." % scope,
        "[signals_width] 180",
        "[sst_expanded] 0",
    ]
    heights = {"vin": 3, "vout_circuit": 5, "vout_model": 5, "error": 4}
    # GTKWave's colour index: 1 red, 2 orange, 3 yellow, 4 green, 5 blue,
    # 6 indigo, 7 violet. Circuit and model differ so they never blur.
    colors = {"vin": 4, "vout_circuit": 3, "vout_model": 2, "error": 7}
    for name, _, _ in SIGNALS:
        rows += ["@200", "-%s" % {"vin": "stimulus",
                                  "vout_circuit": "circuit (ngspice)",
                                  "vout_model": "model (xezim)",
                                  "error": "model - circuit"}[name]]
        rows += ["[color] %d" % colors[name],
                 GTKW_STEP if name == "vin" else GTKW_ANALOG,
                 "%s.%s" % (scope, name), GTKW_STRETCH]
        rows += ["-"] * heights[name]
    rows += ["[pattern_trace] 1", "[pattern_trace] 0", ""]
    Path(path).write_text("\n".join(rows))


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------
INK, MUTED, GRID = "#1f2328", "#59636e", "#d8dee4"
C_CIRCUIT, C_MODEL, C_VIN, C_ERR = "#5b8fd6", "#c4471d", "#9aa4ae", "#7a4fb5"


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw),
               default=10 * mag)
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + step * 1e-9:
        out.append(round(t, 12))
        t += step
    return out


def fmt(v):
    s = ("%.4g" % v)
    return "0" if s in ("-0", "0") else s.replace("-", "−")


def thin(tr, t0, t1, px):
    """Keep the shape at screen resolution: per pixel column, the first,
    min, max and last point in time order, so no peak is lost."""
    pts = [p for p in tr if t0 <= p[0] <= t1]
    if len(pts) <= 4 * px:
        return pts
    out, w, i = [], (t1 - t0) / px, 0
    for k in range(px):
        hi = t0 + (k + 1) * w
        b = []
        while i < len(pts) and pts[i][0] <= hi:
            b.append(pts[i])
            i += 1
        if b:
            keep = {0, len(b) - 1,
                    min(range(len(b)), key=lambda j: b[j][1]),
                    max(range(len(b)), key=lambda j: b[j][1])}
            out += [b[j] for j in sorted(keep)]
    return out


class Panel:
    def __init__(self, x, y, w, h, t0, t1, vlo, vhi, tscale, tunit):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.t0, self.t1, self.vlo, self.vhi = t0, t1, vlo, vhi
        self.ts, self.tu = tscale, tunit

    def X(self, t):
        return self.x + (t - self.t0) / (self.t1 - self.t0) * self.w

    def Y(self, v):
        # clamped to the panel: an off-scale point pins to the edge
        v = min(max(v, self.vlo), self.vhi)
        return self.y + self.h - (v - self.vlo) / (self.vhi - self.vlo) * self.h

    def path(self, tr, color, width, opacity=1.0, dash=None):
        pts = thin(tr, self.t0, self.t1, int(self.w))
        if len(pts) < 2:
            return ""
        d = "M" + " L".join("%.1f %.1f" % (self.X(t), self.Y(v)) for t, v in pts)
        extra = ' stroke-dasharray="%s"' % dash if dash else ""
        return ('<path d="%s" fill="none" stroke="%s" stroke-width="%s" '
                'stroke-opacity="%s" stroke-linejoin="round"%s/>'
                % (d, color, width, opacity, extra))

    def frame(self, ylabel, xlabel=True, yfmt=fmt):
        s = []
        for v in nice_ticks(self.vlo, self.vhi, 4):
            if self.vlo <= v <= self.vhi:
                y = self.Y(v)
                s.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" '
                         'stroke="%s"/>' % (self.x, self.x + self.w, y, y, GRID))
                s.append('<text x="%.1f" y="%.1f" text-anchor="end" '
                         'class="tick">%s</text>' % (self.x - 6, y + 4, yfmt(v)))
        for t in nice_ticks(self.t0 * self.ts, self.t1 * self.ts, 6):
            x = self.X(t / self.ts)
            if self.x - 0.5 <= x <= self.x + self.w + 0.5:
                s.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" '
                         'stroke="%s"/>' % (x, x, self.y, self.y + self.h, GRID))
                if xlabel:
                    s.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                             'class="tick">%s</text>'
                             % (x, self.y + self.h + 16, fmt(t)))
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                 'fill="none" stroke="%s"/>' % (self.x, self.y, self.w, self.h,
                                                MUTED))
        s.append('<text x="%.1f" y="%.1f" class="axis" transform="rotate(-90 '
                 '%.1f %.1f)" text-anchor="middle">%s</text>'
                 % (self.x - 46, self.y + self.h / 2, self.x - 46,
                    self.y + self.h / 2, ylabel))
        if xlabel:
            s.append('<text x="%.1f" y="%.1f" class="axis" text-anchor="middle">'
                     'time (%s)</text>' % (self.x + self.w / 2,
                                           self.y + self.h + 34, self.tu))
        return "\n".join(s)


def span(trs, t0, t1, pad=0.08):
    vs = [v for tr in trs for t, v in tr if t0 <= t <= t1]
    lo, hi = min(vs), max(vs)
    if hi - lo < 1e-15:
        hi, lo = hi + 1e-3, lo - 1e-3
    p = (hi - lo) * pad
    return lo - p, hi + p


def tunit(dt):
    for scale, unit in ((1e9, "ns"), (1e6, "µs"), (1e3, "ms")):
        if dt * scale < 5000:
            return scale, unit
    return 1.0, "s"


def legend(x, y, items):
    s, cx = [], x
    for label, color, width, op in items:
        s.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" '
                 'stroke-width="%s" stroke-opacity="%s"/>'
                 % (cx, cx + 26, y, y, color, width, op))
        s.append('<text x="%.1f" y="%.1f" class="leg">%s</text>'
                 % (cx + 32, y + 4, label))
        cx += 40 + 7.2 * len(label)
    return "\n".join(s)


def svg_doc(w, h, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" font-family="-apple-system, Segoe UI, '
            'Helvetica, Arial, sans-serif">\n<style>'
            '.title{font-size:17px;font-weight:600;fill:%s}'
            '.sub{font-size:13px;fill:%s}.tick{font-size:11px;fill:%s}'
            '.axis{font-size:12px;fill:%s}.leg{font-size:12.5px;fill:%s}'
            '.note{font-size:11.5px;fill:%s;font-style:italic}'
            '</style>\n<rect width="100%%" height="100%%" fill="#ffffff"/>\n'
            '%s\n</svg>\n' % (w, h, w, h, INK, MUTED, MUTED, MUTED, INK, MUTED,
                              body))


def score_line(sc):
    return ("rms error %.2f%% of the circuit's swing (pass mark 15%%), "
            "worst single point %.1f%%: %s"
            % (sc["rms"] * 100, sc["max"] * 100, sc["verdict"]))


def plot_prbs(d, err, path):
    W, H, L, R = 1000, 560, 78, 24
    c, m, vin = d["circuit"], d["model"], d["vin"]
    t0, t1 = 0.0, min(c[-1][0], m[-1][0])
    ts, tu = tunit(t1)
    vlo, vhi = span([c, m, vin], t0, t1)
    top = Panel(L, 76, W - L - R, 300, t0, t1, vlo, vhi, ts, tu)
    errm = [(t, v * 1e3) for t, v in err]
    st = d["score"]["settle"]
    # Scaled to the SCORED stretch: the start-up reaches about a volt and,
    # left in, flattens the residual that is actually being judged.
    lim = max(abs(e) for t, e in errm if t >= st) * 1.25
    bot = Panel(L, 410, W - L - R, 100, t0, t1, -lim, lim, ts, tu)
    shade = ""
    if st:
        for p in (top, bot):
            shade += ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                      'fill="#eef1f4"/>' % (p.x, p.y, p.X(st) - p.x, p.h))
        shade += ('<text x="%.1f" y="%.1f" class="note" text-anchor="middle">'
                  'not scored: the model starts from rest</text>'
                  % ((top.x + top.X(st)) / 2, top.y + 16))
        shade += ('<text x="%.1f" y="%.1f" class="note" text-anchor="middle">'
                  'start-up error runs off this scale</text>'
                  % ((bot.x + bot.X(st)) / 2, bot.y + 14))
    body = "\n".join([
        '<text x="%d" y="28" class="title">%s</text>' % (L, d["title"]),
        '<text x="%d" y="48" class="sub">%s</text>' % (L, score_line(d["score"])),
        legend(L, 64, [("stimulus", C_VIN, 1.2, 1), ("circuit (ngspice)",
                       C_CIRCUIT, 6, 0.45), ("model (xezim)", C_MODEL, 1.6, 1)]),
        shade,
        top.frame("volts", xlabel=False), bot.frame("error (mV)"),
        top.path(vin, C_VIN, 1.2),
        top.path(c, C_CIRCUIT, 6, 0.45),
        top.path(m, C_MODEL, 1.6),
        bot.path(errm, C_ERR, 1.2),
    ])
    Path(path).write_text(svg_doc(W, H, body))


def worst_windows(err, t_from, t_end, n=2, blocks=32):
    """The n stretches where the settled model is furthest from the
    circuit: split the run into blocks, rank them by worst |error| after
    start-up, keep the top n that are not neighbours, and widen each to
    two blocks so the disagreement has context on both sides."""
    w = t_end / blocks
    peak = []
    for k in range(blocks):
        a, b = k * w, (k + 1) * w
        es = [abs(e) for t, e in err if a <= t < b and t >= t_from]
        if es:
            peak.append((max(es), k))
    picked = []
    for _, k in sorted(peak, reverse=True):
        if all(abs(k - j) > 2 for j in picked):
            picked.append(k)
        if len(picked) == n:
            break
    out = []
    for k in sorted(picked):
        # centre on the block's worst point, one block either side
        es = [(abs(e), t) for t, e in err if k * w <= t < (k + 1) * w]
        tc = max(es)[1]
        a = max(t_from, tc - w)
        b = min(t_end, a + 2 * w)
        out.append((b - 2 * w if b - a < 2 * w else a, b))
    return out


def settled_score(d, t_from):
    c, m = d["circuit"], d["model"]
    es = [mv - interp(c, t) for t, mv in m if t >= t_from]
    cs = [v for t, v in c if t >= t_from]
    exc = max(cs) - min(cs)
    return (math.sqrt(sum(e * e for e in es) / len(es)) / exc,
            max(abs(e) for e in es) / exc, exc)


def plot_chirp(d, err, path):
    W, H, L, R, G = 1000, 848, 78, 24, 56
    c, m, vin = d["circuit"], d["model"], d["vin"]
    t_end = min(c[-1][0], m[-1][0])
    st = d["score"]["settle"]
    errm = [(t, v * 1e3) for t, v in err]
    wins = worst_windows(err, st, t_end)
    d["wins"] = wins  # the web page draws the same boxes
    s_rms, s_max, _ = settled_score(d, st)
    d["score"]["settled"] = (s_rms, s_max)
    late = [abs(e) for t, e in errm if t >= st]
    lim = max(late) * 1.25
    ts, tu = tunit(t_end)
    W2 = W - L - R
    over = Panel(L, 108, W2, 230, 0, t_end, *span([c, m, vin], 0, t_end), ts, tu)
    oerr = Panel(L, 356, W2, 80, 0, t_end, -lim, lim, ts, tu)
    shade = ""
    for p in (over, oerr):
        shade += ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                  'fill="#eef1f4"/>' % (p.x, p.y, max(2.0, p.X(st) - p.x), p.h))
    first = max(errm[:2000], key=lambda p: abs(p[1]))
    d["score"]["startup"] = (interp(m, first[0]), interp(c, first[0]),
                             catch_up_time(err, d["score"]["norm"]))
    body = [
        '<text x="%d" y="28" class="title">%s</text>' % (L, d["title"]),
        '<text x="%d" y="48" class="sub">%s</text>' % (L, score_line(d["score"])),
        '<text x="%d" y="66" class="sub">After start-up (from %.0f ns): rms '
        '%.2f%%, worst point %.2f%%. The whole-run figures above include the '
        'model waking up from rest.</text>' % (L, st * 1e9, s_rms * 100,
                                               s_max * 100),
        legend(L, 86, [("stimulus", C_VIN, 1.2, 1), ("circuit (ngspice)",
                       C_CIRCUIT, 6, 0.45), ("model (xezim)", C_MODEL, 1.6, 1)]),
        shade,
        over.frame("volts", xlabel=False), oerr.frame("error (mV)"),
    ]
    for k, (a, b) in enumerate(wins):
        for p in (over, oerr):
            body.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                        'fill="none" stroke="%s" stroke-dasharray="4 3"/>'
                        % (p.X(a), p.y, p.X(b) - p.X(a), p.h, INK))
        body.append('<text x="%.1f" y="%.1f" class="leg" text-anchor="middle">'
                    '%s</text>' % ((over.X(a) + over.X(b)) / 2, over.y - 4,
                                   "AB"[k]))
    body += [
        over.path(vin, C_VIN, 1.2),
        over.path(c, C_CIRCUIT, 6, 0.45),
        over.path(m, C_MODEL, 1.6),
        oerr.path(errm, C_ERR, 1.2),
        '<text x="%.1f" y="%.1f" class="note">start-up: the model begins at '
        '%.2f V while the circuit sits at %.2f V (off this scale)</text>'
        % (oerr.X(st) + 6, oerr.y + 14, interp(m, first[0]),
           interp(c, first[0])),
    ]
    pw = (W2 - G) / 2
    for k, (a, b) in enumerate(wins):
        x = L + k * (pw + G)
        zs, zu = tunit(b - a)
        vw = [v for t, v in vin if a <= t <= b]
        rng = d.get("in_range")
        if rng and max(vw) > rng[1]:
            where = ("input reaches %.3f V, past the measured %g V: the "
                     "clamp skips the filter" % (max(vw), rng[1]))
        elif rng and min(vw) < rng[0]:
            where = ("input dips to %.3f V, below the measured %g V: the "
                     "clamp skips the filter" % (min(vw), rng[0]))
        else:
            where = "inside the measured range"
        d.setdefault("windows", []).append(where != "inside the measured range")
        top = Panel(x, 518, pw, 190, a, b, *span([c, m], a, b), zs, zu)
        lz = max(abs(e) for t, e in errm if a <= t <= b) * 1.25
        bot = Panel(x, 726, pw, 70, a, b, -lz, lz, zs, zu)
        body += [
            '<text x="%.1f" y="494" class="sub">%s: worst error %.1f mV</text>'
            % (x, "AB"[k], lz / 1.25),
            '<text x="%.1f" y="510" class="note">%s</text>' % (x, where),
            top.frame("volts", xlabel=False), bot.frame("error (mV)"),
            top.path(c, C_CIRCUIT, 6, 0.45),
            top.path(m, C_MODEL, 1.6),
            bot.path(errm, C_ERR, 1.2),
        ]
    Path(path).write_text(svg_doc(W, H, "\n".join(body)))


PLOTS = {"prbs": plot_prbs, "chirp": plot_chirp}


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case", choices=sorted(CASES))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = a.out or RUNS / ("%s_wave" % a.case)
    if out.exists():
        shutil.rmtree(out)  # start empty: a stale file must never ride along
    out.mkdir(parents=True)

    readme = [
        "%s: the circuit and its model, side by side" % a.case,
        "=" * 60,
        "",
        "Each stimulus has four files:",
        "  *.html  the waveforms as a web page: open it in any browser and",
        "          drag across the plot to zoom (nothing to install)",
        "  *.svg   the same comparison as a still picture",
        "  *.fst   the waveforms for a waveform viewer (GTKWave, Surfer)",
        "  *.gtkw  a GTKWave layout that draws them as curves",
        "",
        "Open one in GTKWave from this folder:",
        "  gtkwave %s_prbs.fst %s_prbs.gtkw" % (a.case, a.case),
        "",
        "Signals (all in volts):",
    ] + ["  %-13s %s" % (n, s) for n, _, s in SIGNALS] + [""]

    for d in CASES[a.case]():
        stem = "%s_%s" % (a.case, d["stim"])
        trim_to_common(d)
        err = with_error(d)
        traces = {"vin": d["vin"], "vout_circuit": d["circuit"],
                  "vout_model": d["model"], "error": err}
        vcd = out / (stem + ".vcd")
        t_last = write_vcd(vcd, a.case, traces)
        wave, note = to_fst(vcd)
        write_gtkw(out / (stem + ".gtkw"), wave.name, a.case, t_last,
                   d["title"])
        PLOTS[d["stim"]](d, err, out / (stem + ".svg"))
        sc = d["score"]
        notes = [
            "Stimulus: %s." % d["what"],
            "Score: %s." % score_line(sc),
            "How it was scored: %s." % sc["how"],
        ] + ([
            "After start-up (from %.0f ns): rms %.2f%%, worst point %.2f%%. "
            "The model's output begins at mid-scale (%.2f V, while the "
            "circuit sits at %.2f V) and takes until %.0f ns to come within "
            "1%% of the circuit, and the whole-run figures include that."
            % (sc["settle"] * 1e9, sc["settled"][0] * 100,
               sc["settled"][1] * 100, sc["startup"][0], sc["startup"][1],
               sc["startup"][2] * 1e9)] if "settled" in sc else []) + ([
            "The two stretches where the settled model is furthest from the "
            "circuit (A and B in the picture) are both where the stimulus "
            "steps outside the %g..%g V input range the model was "
            "characterised over (it reaches %.3f..%.3f V). There the model "
            "adds clamp(input) - input straight onto its output, outside "
            "its filter (rc_lpf2_rnm.sv, final_out = static_out + "
            "(dynamic_out - GAIN_DC*u_dev)), so the output jumps by the "
            "input's excess instantly, sharp corners included, which no RC "
            "filter can do. The error in those stretches is that excess, "
            "sample for sample: a property of where the model applies its "
            "clamp, not of its filter, and only outside the measured range."
            % (d["in_range"] + (min(v for _, v in d["vin"]),
                                max(v for _, v in d["vin"])))]
            if d.get("windows") and all(d["windows"]) else [])
        page = out / (stem + ".html")
        write_page(page, d, err, [n for n in notes if not n.startswith("Score:")],
                   {"vin": C_VIN, "circuit": C_CIRCUIT, "model": C_MODEL,
                    "error": C_ERR}, score_line(sc))
        readme += ["%s" % d["title"], "-" * len(d["title"])] + notes + [
            "Files: %s, %s.gtkw, %s.svg, %s (%.1f MB of waveform; the "
            "page opens in any browser and zooms)"
            % (wave.name, stem, stem, page.name, wave.stat().st_size / 1e6),
        ] + (["Note: " + note] if note else []) + [""]
        print("  %-22s %6.2f MB   %s" % (wave.name, wave.stat().st_size / 1e6,
                                         score_line(sc)))
        print("  %-22s %6.2f MB   zoomable in any browser"
              % (page.name, page.stat().st_size / 1e6))
    readme += [
        "Every trace and number above comes from one demo run's own output",
        "files; nothing was re-simulated to make this folder.",
        "",
    ]
    (out / "README.txt").write_text("\n".join(readme))
    print("  bundle: %s" % out)


if __name__ == "__main__":
    sys.exit(main())
