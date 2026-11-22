"""Self-contained web pages of waveforms: zoom in any browser, with nothing
to install and nothing fetched from the network.

The data rides inside the page. Every point the run wrote is kept, packed
as differences from the point before (a smooth waveform barely changes
from one sample to the next, so the differences are small numbers) and
then gzip-compressed: times to 1 fs, voltages to 0.1 uV. The browser
unpacks it with DecompressionStream (Chrome/Edge 80+, Firefox 113+,
Safari 16.4+) and draws it on a canvas, thinning to one min/max pair per
pixel column when a stretch holds more points than the screen can show.

One page builder, write_spec_page(), takes a description of the panels,
traces, check marks and shaded windows. Two layouts use it:

  write_page()  circuit vs model under one stimulus, with their
                difference underneath (wave_bundle.py)
  the UVM-MS run: stimulus, model response, what ngspice says each
                check should read, and every check's error against its
                tolerance (uvm_wave.py)

Standard library only.
"""
import base64
import gzip
import html
import json
import struct
from pathlib import Path

T_SCALE = 1e15   # seconds -> fs
V_SCALE = 1e7    # volts -> 0.1 uV
GAP = -2 ** 31   # a value token meaning "no value here": the line breaks

DEFAULT_HELP = (
    "Drag across the plot to zoom into that stretch. Scroll to zoom around "
    "the pointer, Shift+scroll (or the arrow keys) to slide along the run, "
    "double-click to see the whole run again. Hover to read every trace at "
    "one instant.")
DEFAULT_FOOTER = (
    "Every point the demo run wrote is in this page (times to 1 fs, voltages "
    "to 0.1 µV); nothing was re-simulated to make it, and it loads "
    "nothing from the network. Built by harness/wave_bundle.py in the "
    "spice2rnm demos.")


def _deltas(xs, times=False):
    """Differences from the previous value, one 32-bit word each.

    Values: a None becomes the GAP token and does not move the running
    value (the line breaks there).
    Times: a step too long for one word (over 2^31 fs, about 2.1 us, as
    when a run holds still) is written as GAP followed by two words,
    high and low, so no time is ever rounded."""
    out, prev = [], 0
    for x in xs:
        if x is None:
            if times:
                raise ValueError("a time cannot be missing")
            out.append(GAP)
            continue
        d = x - prev
        prev = x
        if times and not (GAP < d < 2 ** 31):
            if d < 0:
                raise ValueError("times must not go backwards")
            out += [GAP, d >> 31, d & (2 ** 31 - 1)]
            continue
        if not (GAP < d < 2 ** 31):
            raise ValueError("a step does not fit in 32 bits")
        out.append(d)
    return out


def _pack(traces):
    """traces: [(key, [(t, v or None), ...])]. Traces on the same time grid
    share one time array. Returns (time meta, trace meta, base64 text)."""
    times, words, meta_t, meta_tr = [], [], [], []

    def add(ints, times=False):
        off = len(words)
        words.extend(_deltas(ints, times))
        return off

    for key, tr in traces:
        ts = [int(round(t * T_SCALE)) for t, _ in tr]
        k = next((i for i, prev in enumerate(times) if prev == ts), None)
        if k is None:
            times.append(ts)
            meta_t.append({"off": add(ts, True), "n": len(ts)})
            k = len(times) - 1
        vs = [None if v is None else int(round(v * V_SCALE)) for _, v in tr]
        meta_tr.append({"key": key, "t": k, "off": add(vs), "n": len(vs)})
    raw = struct.pack("<%di" % len(words), *words)
    z = gzip.compress(raw, 9, mtime=0)  # mtime=0: same run, same bytes
    b64 = base64.b64encode(z).decode()
    wrapped = "\n".join(b64[i:i + 120] for i in range(0, len(b64), 120))
    return meta_t, meta_tr, wrapped


def write_spec_page(path, spec, colors):
    """spec:
      title, score, notes [str], help (opt), footer (opt)
      traces  [{key, label, legend (opt), pts, color, w, a}]
              color is a CSS colour name below: vin circuit model error
      panels  [{id, ylabel, keys, mul (1), unit ('V'), sym, skip_startup,
                ratio, height}]   ratio: a 0-based "error / tolerance" axis
      marks   [{t, panel, y, color, kind ('dot'|'ring'), text}]
      shades  [{a, b, label}]  boxes [{a, b, label}]  hlines [{panel, y, label}]
      presets [{label, a, b}]  settle  t1  legend_marks [{color, kind, label}]
    """
    meta_t, meta_tr, blob = _pack([(tr["key"], tr["pts"])
                                   for tr in spec["traces"]])
    for m, tr in zip(meta_tr, spec["traces"]):
        m.update({k: tr[k] for k in ("label", "color", "w", "a")})
    panels = []
    for p in spec["panels"]:
        panels.append({"id": p["id"], "ylabel": p["ylabel"], "keys": p["keys"],
                       "mul": p.get("mul", 1), "unit": p.get("unit", "V"),
                       "sym": bool(p.get("sym")),
                       "skip": bool(p.get("skip_startup")),
                       "ratio": bool(p.get("ratio")),
                       "h": p.get("height", 200)})
    meta = {"times": meta_t, "traces": meta_tr, "tscale": 1 / T_SCALE,
            "vscale": 1 / V_SCALE, "gap": GAP, "panels": panels,
            "t0": 0.0, "t1": spec["t1"], "settle": spec.get("settle") or 0.0,
            "presets": spec.get("presets", []), "boxes": spec.get("boxes", []),
            "shades": spec.get("shades", []), "hlines": spec.get("hlines", []),
            "marks": spec.get("marks", [])}
    legend = []
    for tr in spec["traces"]:
        if tr.get("legend") is False:
            continue
        legend.append('<span><i style="border-color: var(--%s); '
                      'border-top-width: %dpx; opacity: %.2f"></i>%s</span>'
                      % (tr["color"], max(3, round(tr["w"])),
                         min(1.0, tr["a"] + 0.1),
                         html.escape(tr.get("legend") or tr["label"])))
    for lm in spec.get("legend_marks", []):
        shape = ("background: var(--%s)" % lm["color"] if lm["kind"] == "dot"
                 else "border: 1.5px solid var(--%s)" % lm["color"])
        legend.append('<span><b class="dot" style="%s"></b>%s</span>'
                      % (shape, html.escape(lm["label"])))
    plots = "\n".join('<div class="plot" id="%s" style="height: %dpx">'
                      '<canvas></canvas><canvas></canvas></div>'
                      % (p["id"], p["h"]) for p in panels)
    page = (PAGE
            .replace("@@TITLE@@", html.escape(spec["title"]))
            .replace("@@SCORE@@", html.escape(spec["score"]))
            .replace("@@LEGEND@@", "\n  ".join(legend))
            .replace("@@PLOTS@@", plots)
            .replace("@@HELP@@", html.escape(spec.get("help") or DEFAULT_HELP))
            .replace("@@NOTES@@", "\n".join("<p>%s</p>" % html.escape(n)
                                            for n in spec["notes"]))
            .replace("@@FOOTER@@", html.escape(spec.get("footer")
                                               or DEFAULT_FOOTER))
            .replace("@@VIN@@", colors["vin"])
            .replace("@@CIRCUIT@@", colors["circuit"])
            .replace("@@MODEL@@", colors["model"])
            .replace("@@ERROR@@", colors["error"])
            .replace("@@META@@", json.dumps(meta))
            .replace("@@DATA@@", blob))
    Path(path).write_text(page)
    return Path(path).stat().st_size


def write_page(path, d, err, notes, colors, score):
    """Circuit vs model under one stimulus (wave_bundle.py's layout)."""
    c, m = d["circuit"], d["model"]
    t1 = min(c[-1][0], m[-1][0])
    st = d["score"].get("settle") or 0.0
    presets = [{"label": "Whole run", "a": 0.0, "b": t1}]
    if st:
        presets.append({"label": "After start-up", "a": st, "b": t1})
    boxes = []
    for k, (a, b) in enumerate(d.get("wins", [])):
        boxes.append({"label": "AB"[k], "a": a, "b": b})
        presets.append({"label": "Box %s" % "AB"[k], "a": a, "b": b})
    if not boxes:
        tw = max(((t, abs(e)) for t, e in err if t >= st),
                 key=lambda p: p[1])[0]
        presets.append({"label": "Worst point", "a": max(0.0, tw - 15e-9),
                        "b": min(t1, tw + 15e-9)})
    spec = {
        "title": d["title"], "score": score, "notes": notes,
        "footer": DEFAULT_FOOTER + (" The same waveforms open in GTKWave "
                                    "from the .fst and .gtkw files."),
        "traces": [
            {"key": "vin", "label": "stimulus", "pts": d["vin"],
             "color": "vin", "w": 1.2, "a": 1},
            {"key": "circuit", "label": "circuit", "legend": "circuit (ngspice)",
             "pts": c, "color": "circuit", "w": 6, "a": 0.45},
            {"key": "model", "label": "model", "legend": "model (xezim)",
             "pts": m, "color": "model", "w": 1.6, "a": 1},
            {"key": "error", "label": "error",
             "legend": "error, model minus circuit", "pts": err,
             "color": "error", "w": 1.2, "a": 1},
        ],
        "panels": [
            {"id": "p-main", "ylabel": "volts",
             "keys": ["vin", "circuit", "model"], "height": 340},
            {"id": "p-err", "ylabel": "error (mV)", "keys": ["error"],
             "mul": 1e3, "unit": "mV", "sym": True, "skip_startup": True,
             "height": 160},
        ],
        "t1": t1, "settle": st, "presets": presets, "boxes": boxes,
    }
    return write_spec_page(path, spec, colors)


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<style>
:root {
  --bg: #ffffff; --ink: #1f2328; --muted: #59636e; --grid: #e4e8ec;
  --frame: #8c959f; --shade: #eef1f4; --win: rgba(122, 79, 181, 0.07);
  --panel: #f6f8fa; --sel: rgba(91, 143, 214, 0.18); --cursor: #1f2328;
  --fail: #cf222e;
  --vin: @@VIN@@; --circuit: @@CIRCUIT@@; --model: @@MODEL@@; --error: @@ERROR@@;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --ink: #e6edf3; --muted: #9198a1; --grid: #21262d;
    --frame: #3d444d; --shade: #161b22; --win: rgba(179, 146, 240, 0.09);
    --panel: #161b22; --sel: rgba(91, 143, 214, 0.28); --cursor: #e6edf3;
    --fail: #ff7b72;
    --vin: #6e7681; --circuit: #4f7fc4; --model: #f0883e; --error: #b392f0;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 24px 16px 40px; }
h1 { font-size: 20px; line-height: 1.3; margin: 0 0 4px; }
.score { color: var(--muted); margin: 0 0 14px; }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 10px 0; }
button { font: inherit; font-size: 13px; padding: 4px 11px; border-radius: 6px;
  border: 1px solid var(--frame); background: var(--panel); color: var(--ink); cursor: pointer; }
button:hover { border-color: var(--ink); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--muted); }
.legend span { white-space: nowrap; }
.legend i { display: inline-block; width: 22px; vertical-align: middle; margin-right: 6px; border-top: 3px solid; }
.legend b.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; vertical-align: middle; margin-right: 6px; }
#readout { font-size: 13px; font-variant-numeric: tabular-nums; color: var(--muted);
  min-height: 22px; margin: 4px 0 0; }
#readout b { color: var(--ink); font-weight: 600; }
#readout2 { font-size: 13px; color: var(--ink); min-height: 20px; margin: 0 0 4px; }
.plot { position: relative; width: 100%; touch-action: none; user-select: none; -webkit-user-select: none; cursor: crosshair; }
.plot canvas { position: absolute; left: 0; top: 0; width: 100%; height: 100%; }
.help { font-size: 13px; color: var(--muted); margin: 6px 0 18px; }
.notes p { margin: 8px 0; max-width: 78ch; }
#status { color: var(--muted); }
footer { font-size: 12.5px; color: var(--muted); margin-top: 26px;
  border-top: 1px solid var(--grid); padding-top: 12px; }
</style>
</head>
<body>
<main>
<h1>@@TITLE@@</h1>
<p class="score">@@SCORE@@</p>
<div class="legend">
  @@LEGEND@@
</div>
<div class="bar" id="presets"></div>
<div id="readout"><span id="status">unpacking the waveforms...</span></div>
<div id="readout2"></div>
@@PLOTS@@
<p class="help">@@HELP@@</p>
<div class="notes">
@@NOTES@@
</div>
<footer>@@FOOTER@@</footer>
</main>
<script type="application/json" id="meta">@@META@@</script>
<script type="text/plain" id="data">
@@DATA@@
</script>
<script>
(async function () {
  "use strict";
  const META = JSON.parse(document.getElementById("meta").textContent);
  const statusEl = document.getElementById("status");
  if (typeof DecompressionStream === "undefined") {
    statusEl.textContent = "This browser is too old to unpack the waveforms " +
      "(it needs DecompressionStream: Chrome or Edge 80+, Firefox 113+, Safari 16.4+).";
    return;
  }
  let I;
  try {
    const b64 = document.getElementById("data").textContent.replace(/\s+/g, "");
    const raw = atob(b64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    I = new Int32Array(await new Response(stream).arrayBuffer());
  } catch (e) {
    statusEl.textContent = "Could not unpack the waveforms: " + e;
    return;
  }
  function undelta(off, n, scale) {
    const o = new Float64Array(n);
    let a = 0;
    for (let i = 0; i < n; i++) {
      const d = I[off + i];
      if (d === META.gap) { o[i] = NaN; continue; }
      a += d; o[i] = a * scale;
    }
    return o;
  }
  function undeltaTime(off, n, scale) {
    // a GAP word here means the step did not fit: the next two words are
    // its high and low halves
    const o = new Float64Array(n);
    let a = 0, w = off;
    for (let i = 0; i < n; i++) {
      const d = I[w++];
      if (d === META.gap) { a += I[w] * 2147483648 + I[w + 1]; w += 2; }
      else a += d;
      o[i] = a * scale;
    }
    return o;
  }
  const T = META.times.map(x => undeltaTime(x.off, x.n, META.tscale));
  const TR = {};
  for (const s of META.traces)
    TR[s.key] = { t: T[s.t], v: undelta(s.off, s.n, META.vscale), label: s.label, color: s.color, w: s.w, a: s.a };

  const PANELS = META.panels.map((p, i) => Object.assign({ idx: i }, p,
    { m: { l: 66, r: 14, t: 10, b: i === META.panels.length - 1 ? 40 : 8 } }));
  const MARKS = META.marks;
  const T0 = META.t0, T1 = META.t1, ST = META.settle;
  let x0 = T0, x1 = T1, hoverT = null, hoverP = null, drag = null, queued = false, showVin = true;

  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  function lb(a, x) { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < x) lo = m + 1; else hi = m; } return lo; }
  function at(tr, t) {
    const a = tr.t, i = lb(a, t);
    if (i <= 0) return tr.v[0];
    if (i >= a.length) return tr.v[a.length - 1];
    const ta = a[i - 1], tb = a[i];
    return tb === ta ? tr.v[i] : tr.v[i - 1] + (tr.v[i] - tr.v[i - 1]) * (t - ta) / (tb - ta);
  }
  function tunit(span) {
    if (span < 2e-9) return [1e12, "ps"];
    if (span < 2e-6) return [1e9, "ns"];
    return [1e6, "µs"];
  }
  function ticks(lo, hi, n) {
    const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw) || raw;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(v);
    return [out, step];
  }
  function dec(step) {
    // enough decimals to print every tick exactly (a 2.5 step needs one more)
    let d = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
    const k = step * Math.pow(10, d);
    if (Math.abs(k - Math.round(k)) > 1e-6) d++;
    return d;
  }
  const keysOf = p => p.keys.filter(k => k !== "vin" || showVin);
  const marksOf = p => MARKS.filter(mk => mk.panel === p.idx);

  for (const p of PANELS) {
    p.box = document.getElementById(p.id);
    [p.base, p.over] = p.box.querySelectorAll("canvas");
  }
  function size() {
    const dpr = window.devicePixelRatio || 1;
    for (const p of PANELS) {
      p.w = p.box.clientWidth; p.h = p.box.clientHeight;
      for (const c of [p.base, p.over]) {
        c.width = Math.round(p.w * dpr); c.height = Math.round(p.h * dpr);
        c.getContext("2d").setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      p.pw = p.w - p.m.l - p.m.r; p.ph = p.h - p.m.t - p.m.b;
    }
  }
  const X = (p, t) => p.m.l + (t - x0) / (x1 - x0) * p.pw;
  const toT = (p, x) => x0 + (x - p.m.l) / p.pw * (x1 - x0);

  function yrange(p) {
    if (p.ratio) {
      // error / tolerance: 0 at the bottom, the fail line (1) always in view
      let hi = 1.25;
      for (const mk of marksOf(p)) if (mk.t >= x0 && mk.t <= x1) hi = Math.max(hi, mk.y * 1.1);
      return [0, hi, false];
    }
    // A panel marked skip ignores the start-up when the view also holds
    // settled data: otherwise a volt of start-up flattens the millivolts
    // that are actually being judged. What it leaves out runs off-scale.
    const skip = p.skip && x0 < ST && x1 > ST + 0.02 * (x1 - x0);
    const from = skip ? ST : x0;
    let lo = Infinity, hi = -Infinity;
    for (const k of keysOf(p)) {
      const tr = TR[k], i0 = Math.max(0, lb(tr.t, from) - 1), i1 = Math.min(tr.t.length - 1, lb(tr.t, x1));
      for (let i = i0; i <= i1; i++) { const v = tr.v[i] * p.mul; if (v < lo) lo = v; if (v > hi) hi = v; }
    }
    for (const mk of marksOf(p)) if (mk.t >= from && mk.t <= x1) { lo = Math.min(lo, mk.y); hi = Math.max(hi, mk.y); }
    if (!isFinite(lo)) { lo = -1; hi = 1; }
    if (p.sym) { const mm = Math.max(Math.abs(lo), Math.abs(hi)) || 1; lo = -mm; hi = mm; }
    if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }
    const pad = (hi - lo) * 0.08;
    return [lo - pad, hi + pad, skip];
  }

  function drawTrace(ctx, p, tr, Y) {
    const t = tr.t, v = tr.v, mul = p.mul;
    const i0 = Math.max(0, lb(t, x0) - 1), i1 = Math.min(t.length - 1, lb(t, x1));
    if (i1 < i0) return;
    ctx.save();
    ctx.globalAlpha = tr.a; ctx.strokeStyle = css("--" + tr.color); ctx.lineWidth = tr.w;
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.beginPath();
    const sx = p.pw / (x1 - x0);
    if (i1 - i0 > p.pw * 3) {
      // More points than pixels: one vertical stroke per pixel column
      // spanning that column's min..max, so no spike is ever thinned away.
      let col = null, mn = 0, mx = 0, first = 0, last = 0, pen = false;
      const flush = () => {
        if (pen) ctx.lineTo(col, Y(first)); else ctx.moveTo(col, Y(first));
        ctx.lineTo(col, Y(mn)); ctx.lineTo(col, Y(mx)); ctx.lineTo(col, Y(last)); pen = true;
      };
      for (let i = i0; i <= i1; i++) {
        const y = v[i] * mul;
        if (y !== y) { if (col !== null) flush(); col = null; pen = false; continue; }
        const x = Math.floor(p.m.l + (t[i] - x0) * sx) + 0.5;
        if (x !== col) { if (col !== null) flush(); col = x; mn = mx = first = last = y; }
        else { if (y < mn) mn = y; if (y > mx) mx = y; last = y; }
      }
      if (col !== null) flush();
    } else {
      let pen = false;
      for (let i = i0; i <= i1; i++) {
        const y = v[i] * mul;
        if (y !== y) { pen = false; continue; }
        const x = p.m.l + (t[i] - x0) * sx;
        if (pen) ctx.lineTo(x, Y(y)); else { ctx.moveTo(x, Y(y)); pen = true; }
      }
    }
    ctx.stroke();
    ctx.restore();
  }

  function drawPanel(p, last) {
    const ctx = p.base.getContext("2d"), m = p.m;
    ctx.clearRect(0, 0, p.w, p.h);
    const [lo, hi, skipped] = yrange(p);
    p.Y = v => m.t + (hi - v) / (hi - lo) * p.ph;
    const Y = p.Y;
    const ink = css("--ink"), muted = css("--muted"), grid = css("--grid");
    ctx.font = "11px -apple-system, Segoe UI, Helvetica, Arial, sans-serif";
    if (ST > x0) {
      ctx.fillStyle = css("--shade");
      const xa = Math.max(m.l, X(p, T0)), xb = Math.min(m.l + p.pw, X(p, ST));
      ctx.fillRect(xa, m.t, xb - xa, p.ph);
    }
    for (const s of META.shades) {
      if (s.b < x0 || s.a > x1) continue;
      const xa = Math.max(m.l, X(p, s.a)), xb = Math.min(m.l + p.pw, X(p, s.b));
      ctx.fillStyle = css("--win"); ctx.fillRect(xa, m.t, Math.max(1, xb - xa), p.ph);
      if (p.idx === 0 && xb - xa > 60) {
        ctx.fillStyle = muted; ctx.textAlign = "center"; ctx.textBaseline = "top";
        ctx.fillText(s.label, (xa + xb) / 2, m.t + 3);
      }
    }
    const [yt, ys] = ticks(lo, hi, p.ratio ? 4 : (p.sym ? 4 : 6)), yd = dec(ys);
    ctx.strokeStyle = grid; ctx.lineWidth = 1; ctx.fillStyle = muted;
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (const v of yt) {
      const y = Math.round(Y(v)) + 0.5;
      ctx.beginPath(); ctx.moveTo(m.l, y); ctx.lineTo(m.l + p.pw, y); ctx.stroke();
      ctx.fillText(v.toFixed(yd), m.l - 6, y);
    }
    const [scale, unit] = tunit(x1 - x0);
    const [xt, xs] = ticks(x0 * scale, x1 * scale, Math.max(3, Math.round(p.pw / 110)));
    const xd = dec(xs);
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (const v of xt) {
      const x = Math.round(X(p, v / scale)) + 0.5;
      ctx.beginPath(); ctx.moveTo(x, m.t); ctx.lineTo(x, m.t + p.ph); ctx.stroke();
      if (last) ctx.fillText(v.toFixed(xd), x, m.t + p.ph + 6);
    }
    if (last) ctx.fillText("time (" + unit + ")", m.l + p.pw / 2, m.t + p.ph + 22);
    ctx.save();
    ctx.translate(14, m.t + p.ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(p.ylabel, 0, 0);
    ctx.restore();
    ctx.save();
    ctx.beginPath(); ctx.rect(m.l, m.t, p.pw, p.ph); ctx.clip();
    for (const k of keysOf(p)) drawTrace(ctx, p, TR[k], Y);
    for (const h of META.hlines) {
      if (h.panel !== p.idx) continue;
      const y = Math.round(Y(h.y)) + 0.5;
      ctx.save(); ctx.setLineDash([5, 4]); ctx.strokeStyle = css("--fail"); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(m.l, y); ctx.lineTo(m.l + p.pw, y); ctx.stroke(); ctx.restore();
      ctx.fillStyle = css("--fail"); ctx.textAlign = "right"; ctx.textBaseline = "bottom";
      ctx.fillText(h.label, m.l + p.pw - 4, y - 2);
    }
    for (const mk of marksOf(p)) {
      if (mk.t < x0 || mk.t > x1) continue;
      const x = X(p, mk.t), y = Y(mk.y), col = css("--" + mk.color);
      ctx.beginPath(); ctx.arc(x, y, mk.kind === "ring" ? 4.5 : 3.2, 0, 2 * Math.PI);
      if (mk.kind === "ring") { ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.stroke(); }
      else { ctx.fillStyle = col; ctx.fill(); }
    }
    ctx.restore();
    for (const b of META.boxes) {
      if (b.b < x0 || b.a > x1) continue;
      const xa = X(p, b.a), xb = X(p, b.b);
      ctx.save(); ctx.setLineDash([4, 3]); ctx.strokeStyle = ink;
      ctx.beginPath(); ctx.rect(xa, m.t, xb - xa, p.ph); ctx.stroke(); ctx.restore();
      if (p.idx === 0) { ctx.fillStyle = ink; ctx.textAlign = "center"; ctx.textBaseline = "top"; ctx.fillText(b.label, (xa + xb) / 2, m.t + 3); }
    }
    if (ST > x0 && X(p, ST) - m.l > 150) {
      ctx.fillStyle = muted; ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.font = "italic 11.5px -apple-system, Segoe UI, Helvetica, Arial, sans-serif";
      const msg = p.skip ? (skipped ? "start-up: runs off this scale" : "start-up") : "not scored: the model starts from rest";
      ctx.fillText(msg, (Math.max(m.l, X(p, T0)) + Math.min(m.l + p.pw, X(p, ST))) / 2, m.t + 4);
    }
    ctx.strokeStyle = css("--frame"); ctx.lineWidth = 1;
    ctx.strokeRect(m.l + 0.5, m.t + 0.5, p.pw, p.ph);
  }

  function nearestMark() {
    if (hoverT === null || hoverP === null) return null;
    let best = null, bd = 7;
    for (const mk of MARKS) {
      if (mk.t < x0 || mk.t > x1 || !mk.text) continue;
      const d = Math.abs(X(hoverP, mk.t) - X(hoverP, hoverT));
      if (d < bd) { bd = d; best = mk; }
    }
    return best;
  }

  function drawOverlay() {
    const mk = nearestMark();
    for (const p of PANELS) {
      const ctx = p.over.getContext("2d"), m = p.m;
      ctx.clearRect(0, 0, p.w, p.h);
      if (drag) {
        const a = Math.max(m.l, Math.min(drag.a, drag.b)), b = Math.min(m.l + p.pw, Math.max(drag.a, drag.b));
        ctx.fillStyle = css("--sel"); ctx.fillRect(a, m.t, b - a, p.ph);
      }
      if (hoverT !== null && hoverT >= x0 && hoverT <= x1) {
        const x = Math.round(X(p, hoverT)) + 0.5;
        ctx.strokeStyle = css("--cursor"); ctx.globalAlpha = 0.5; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, m.t); ctx.lineTo(x, m.t + p.ph); ctx.stroke(); ctx.globalAlpha = 1;
      }
      if (mk && p.Y) {
        for (const o of MARKS) {
          if (o.t !== mk.t || o.panel !== p.idx) continue;
          ctx.beginPath(); ctx.arc(X(p, o.t), p.Y(o.y), 7, 0, 2 * Math.PI);
          ctx.strokeStyle = css("--ink"); ctx.lineWidth = 1.5; ctx.stroke();
        }
      }
    }
  }

  const readout = document.getElementById("readout"), readout2 = document.getElementById("readout2");
  function fmtVal(k, v) {
    const p = PANELS.find(q => q.keys.includes(k));
    if (v !== v) return "–";
    if (p && p.mul !== 1) { const x = v * p.mul; return (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(2) + " " + p.unit; }
    return v.toFixed(4) + " V";
  }
  function showReadout() {
    const mk = nearestMark();
    readout2.textContent = mk ? mk.text : "";
    if (hoverT === null) {
      const [s, u] = tunit(x1 - x0);
      readout.innerHTML = "showing <b>" + (x0 * s).toFixed(1) + " to " + (x1 * s).toFixed(1) + " " + u +
        "</b> of " + (T1 * 1e9).toFixed(0) + " ns. Hover to read values.";
      return;
    }
    const [s, u] = tunit(x1 - x0), fine = dec((x1 - x0) * s / 1000);
    let h = "t = <b>" + (hoverT * s).toFixed(Math.min(fine, 4)) + " " + u + "</b>";
    for (const k of Object.keys(TR)) h += " &nbsp; " + TR[k].label + " <b>" + fmtVal(k, at(TR[k], hoverT)) + "</b>";
    readout.innerHTML = h;
  }

  function redraw() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      PANELS.forEach((p, i) => drawPanel(p, i === PANELS.length - 1));
      drawOverlay(); showReadout();
    });
  }
  function view(a, b) {
    const minSpan = 20e-12, full = T1 - T0;
    let span = Math.max(minSpan, Math.min(full, b - a));
    let c = (a + b) / 2;
    a = c - span / 2; b = c + span / 2;
    if (a < T0) { b += T0 - a; a = T0; }
    if (b > T1) { a -= b - T1; b = T1; }
    x0 = Math.max(T0, a); x1 = Math.min(T1, b);
    redraw();
  }

  for (const p of PANELS) {
    const box = p.box, px = e => e.clientX - box.getBoundingClientRect().left;
    box.addEventListener("pointerdown", e => {
      if (e.button !== 0) return;
      drag = { a: px(e), b: px(e) };
      try { box.setPointerCapture(e.pointerId); } catch (err) { /* keep going without capture */ }
    });
    box.addEventListener("pointermove", e => {
      const x = px(e);
      hoverT = (x >= p.m.l && x <= p.m.l + p.pw) ? toT(p, x) : null;
      hoverP = p;
      if (drag) drag.b = x;
      drawOverlay(); showReadout();
    });
    box.addEventListener("pointerup", () => {
      if (drag && Math.abs(drag.b - drag.a) > 4) {
        const a = toT(p, Math.min(drag.a, drag.b)), b = toT(p, Math.max(drag.a, drag.b));
        drag = null; view(a, b);
      } else { drag = null; drawOverlay(); }
    });
    box.addEventListener("pointerleave", () => { if (!drag) { hoverT = null; drawOverlay(); showReadout(); } });
    box.addEventListener("dblclick", () => view(T0, T1));
    box.addEventListener("wheel", e => {
      e.preventDefault();
      const span = x1 - x0;
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const d = (Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY) / p.pw * span;
        view(x0 + d, x1 + d);
      } else {
        const tc = toT(p, px(e)), f = Math.exp(e.deltaY * 0.0015);
        view(tc - (tc - x0) * f, tc + (x1 - tc) * f);
      }
    }, { passive: false });
  }
  document.addEventListener("keydown", e => {
    const span = x1 - x0;
    if (e.key === "ArrowLeft") view(x0 - span * 0.2, x1 - span * 0.2);
    else if (e.key === "ArrowRight") view(x0 + span * 0.2, x1 + span * 0.2);
    else if (e.key === "+" || e.key === "=") view(x0 + span * 0.25, x1 - span * 0.25);
    else if (e.key === "-") view(x0 - span * 0.5, x1 + span * 0.5);
    else return;
    e.preventDefault();
  });

  const bar = document.getElementById("presets");
  let vinBtn = null;
  function setVin(v) {
    showVin = v;
    if (vinBtn) vinBtn.textContent = showVin ? "Hide stimulus" : "Show stimulus";
  }
  // A preset may say whether the stimulus is shown (a tone whose response
  // is far smaller than its drive); on such a page the others show it.
  const vinPresets = META.presets.some(pr => "vin" in pr);
  for (const pr of META.presets) {
    const b = document.createElement("button");
    b.textContent = pr.label;
    b.addEventListener("click", () => {
      if ("vin" in pr) setVin(pr.vin); else if (vinPresets) setVin(true);
      view(pr.a, pr.b);
    });
    bar.appendChild(b);
  }
  const out = document.createElement("button");
  out.textContent = "Zoom out";
  out.addEventListener("click", () => { const s = x1 - x0; view(x0 - s / 2, x1 + s / 2); });
  bar.appendChild(out);
  if (PANELS.some(p => p.keys.includes("vin"))) {
    // The stimulus can swing far wider than the response; hiding it lets
    // the volts axis fit the traces being compared.
    vinBtn = document.createElement("button");
    vinBtn.textContent = "Hide stimulus";
    vinBtn.addEventListener("click", () => { setVin(!showVin); redraw(); });
    bar.appendChild(vinBtn);
  }

  new ResizeObserver(() => { size(); redraw(); }).observe(document.querySelector("main"));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
  size(); redraw();
  // For anyone who wants the numbers: in the browser console,
  // waveforms.traces.model.t / .v are the model's times (s) and volts.
  window.waveforms = { traces: TR, marks: MARKS, view: view, get range() { return [x0, x1]; } };
})();
</script>
</body>
</html>
"""
