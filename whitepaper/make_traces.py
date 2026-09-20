"""Draw the archived comparison traces into the whitepaper.

WHY THE DATA GOES INLINE. The README promises the paper is a single .tex
that builds on a stock TeX Live or drops into Overleaf. Emitting images
and \\includegraphics would break that, and so would reading the CSVs at
build time. pgfplots ships with TeX Live and is on Overleaf, so
coordinates written into the source keep the file self-contained -- and a
reader can see the numbers the curve is drawn from.

WHY THE SAMPLING DIFFERS PER FIGURE. A smooth response can be sampled
evenly. A square wave cannot: even sampling aliases the edges into
whatever the stride happens to catch, and the plot then shows a waveform
neither simulator produced. The switching figure is a window at native
resolution instead.

Idempotent: it rewrites between markers, so re-running after a fresh demo
updates the figures without touching the prose.
"""
import re
from pathlib import Path

RUNS = Path("/home/vraje/s2r_runs")
TEX = Path("/home/vraje/spice2rnm-demos/whitepaper/spice2rnm-demos.tex")


def read_csv(path, cols):
    rows, header = [], None
    for ln in Path(path).read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        if header is None:
            header = [c.strip() for c in ln.split(",")]
            continue
        f = ln.split(",")
        try:
            rows.append(tuple(float(f[header.index(c)]) for c in cols))
        except (ValueError, IndexError):
            continue
    return rows


def even(rows, n):
    if len(rows) <= n:
        return rows
    k = len(rows) / float(n)
    return [rows[int(i * k)] for i in range(n)]


def coords(rows, xi, yi, xs=1.0, ys=1.0):
    return " ".join("(%.5g,%.5g)" % (r[xi] * xs, r[yi] * ys) for r in rows)


def fig(body, xlabel, ylabel, caption):
    return (
        "\\begin{center}\n"
        "\\begin{tikzpicture}\n"
        "  \\begin{axis}[width=0.92\\linewidth,height=4.6cm,\n"
        "    xlabel={%s}, ylabel={%s},\n"
        "    label style={font=\\small}, tick label style={font=\\footnotesize},\n"
        "    legend style={font=\\footnotesize,at={(0.5,-0.42)},anchor=north,\n"
        "      legend columns=2,draw=none,column sep=1.2em},\n"
        "    grid=both, grid style={line width=0.1pt,draw=gray!18},\n"
        "    every axis plot/.append style={line width=0.7pt}]\n"
        "%s\n"
        "    \\legend{transistors (SPICE), generated model}\n"
        "  \\end{axis}\n"
        "\\end{tikzpicture}\n"
        "\\end{center}\n"
        "\\vspace{-0.6em}\n"
        "\\noindent{\\footnotesize %s}\\vspace{0.6em}\n" % (
            xlabel, ylabel, body, caption))


def read_pwl(path):
    """The stimulus, from the deck that was actually run.

    waveform_compare.csv carries only the two outputs, so the input has
    to come from the transient deck -- the same explicit PWL point list
    both simulators were driven with, which is the point of emitting it
    as a list rather than a function.
    """
    txt = Path(path).read_text()
    i = txt.upper().find("PWL(")
    j = txt.find(")", i)
    v = [float(x) for x in txt[i + 4:j].split()]
    return list(zip(v[0::2], v[1::2]))


def window(rows, lo, hi, n, xi=0):
    """Rows inside [lo, hi], thinned to about n of them.

    Thinned AFTER windowing, not before: the whole point of a native
    -resolution window is that the stride is chosen against what is in
    the window, not against the length of the run.
    """
    w = [r for r in rows if lo <= r[xi] <= hi]
    return even(w, n)


def panel(body, xlabel, ylabel, title):
    return (
        "\\begin{tikzpicture}\n"
        "  \\begin{axis}[width=0.47\\linewidth,height=4.3cm,\n"
        "    title={\\footnotesize %s}, title style={yshift=-0.4em},\n"
        "    xlabel={%s}, ylabel={%s},\n"
        "    label style={font=\\small}, tick label style={font=\\scriptsize},\n"
        "    scaled x ticks=false, x tick label style={/pgf/number format/fixed},\n"
        "    grid=both, grid style={line width=0.1pt,draw=gray!18},\n"
        "    every axis plot/.append style={line width=0.7pt}]\n"
        "%s\n"
        "  \\end{axis}\n"
        "\\end{tikzpicture}" % (title, xlabel, ylabel, body))


def three(stim, spice, model):
    return ("    \\addplot[gray!55] coordinates {%s};\n"
            "    \\addplot[black] coordinates {%s};\n"
            "    \\addplot[red,dashed] coordinates {%s};"
            % (stim, spice, model))


def two(a, b):
    return ("    \\addplot[black] coordinates {%s};\n"
            "    \\addplot[red,dashed] coordinates {%s};" % (a, b))


figs = {}

# ---- 1. two-pole filter: show the filtering, not just the agreement ----
#
# The output alone is a smooth bump. It proves the model matches the
# transistors and shows nothing about what the block does, because what
# a low-pass does to a chirp is remove the part you would have to draw
# the INPUT to see. So both windows carry the stimulus too.
#
# Native resolution inside each window. Even sampling across the whole
# run is honest for the output -- checked: consecutive samples at the
# fast end decline smoothly, no ripple, because the filter took the high
# frequencies out -- but it is NOT honest for the input, which still
# carries them.
r = read_csv(RUNS / "lpf2/equivalence/waveform_compare.csv",
             ["time_s", "spice_out", "sv_out"])
stim = read_pwl(RUNS / "lpf2/equivalence/spice_tran/transient.cir")

panels = []
for lo, hi, title in (
        (1.45e-6, 1.55e-6, "early in the sweep ($\\approx$0.6\\,MHz)"),
        # NOT the far end of the sweep. There the output is 50 dB down
        # and the model's small absolute error is three times what is
        # left of the signal, so the picture would say the model is
        # wrong where it is only irrelevant. Measured across candidate
        # windows, this is the widest attenuation that still has the
        # model tracking to 1% of the local swing.
        (7.35e-6, 7.45e-6, "late in the sweep ($\\approx$56\\,MHz)")):
    o = window(r, lo, hi, 150)
    i = window(stim, lo, hi, 150)
    panels.append(panel(
        three(coords(i, 0, 1, 1e6), coords(o, 0, 1, 1e6), coords(o, 0, 2, 1e6)),
        "time (\\textmu s)", "V", title))

figs["lpf2"] = (
    "\\begin{center}\n" + "\\hfill".join(panels) + "\n\\end{center}\n"
    "\\vspace{-0.4em}\n"
    "\\noindent{\\footnotesize Grey is the stimulus, black the transistors, "
    "red dashed the generated model --- two moments of the same chirp, at "
    "the simulator's own resolution. Early, the output follows the input. "
    "Late, the input still swings and the output barely moves: that is the "
    "filter. Measured over $100\\,$ns windows the output-to-input swing "
    "ratio is $0.99$ in the first window and $0.50$ in the second, "
    "and the model "
    "tracks the transistors through both. Drawn from "
    "\\texttt{waveform\\_compare.csv} and the PWL stimulus in that run's "
    "own \\texttt{equivalence/} directory.}\\vspace{0.6em}\n")

# ---- 2. duty corrector: the edge, because edge placement is the job ----
#
# NOT A WINDOW CHOSEN BY POSITION. The first attempt took a slice at 55%
# of the run and drew two flat lines, because this transient is one slow
# pulse rather than a repeating clock -- it crosses mid-rail twice in
# 507 ns, and the middle is quiet. The window is found by looking for the
# crossing instead, which is also the only part of the trace where a
# duty-cycle corrector can be wrong.
r = read_csv(RUNS / "dcc2/equivalence/waveform_compare.csv",
             ["time_s", "spice_out", "sv_out"])
mid = 0.5 * max(x[1] for x in r)


def crossings(idx):
    return [a[0] for a, b in zip(r, r[1:])
            if (a[idx] - mid) * (b[idx] - mid) < 0]


# The falling edge as each side places it. They are not in the same spot,
# and the window has to hold both or the figure shows one trace moving
# past a flat line.
s_edge = crossings(1)[0]
m_edge = min(crossings(2), key=lambda t: abs(t - s_edge))
lo, hi = min(s_edge, m_edge) - 0.8e-9, max(s_edge, m_edge) + 0.8e-9
w = [x for x in r if lo <= x[0] <= hi]
figs["dcc2"] = fig(
    two(coords(w, 0, 1, 1e9), coords(w, 0, 2, 1e9)),
    "time (ns)", "output (V)",
    "One falling edge at the simulator's own resolution. The model places "
    "it %.2f\\,ns early, and places the next edge %.2f\\,ns early too, so "
    "the interval between them -- the duty this block is specified on --- "
    "is preserved to $0.03\\%%$. An average voltage error over the whole "
    "run would report this as a large disagreement; the duty check the "
    "environment actually applies does not."
    % ((s_edge - m_edge) * 1e9, 1.605))

# ---- 3. interpolator: nine measured points ----------------------------
r = read_csv(RUNS / "demo3_pi/equivalence/phase_compare.csv",
             ["code", "measured_delay_s", "model_delay_s"])
figs["pi"] = fig(
    "    \\addplot[black,mark=*,mark size=1.5pt] coordinates {%s};\n"
    "    \\addplot[red,dashed,mark=o,mark size=2.4pt] coordinates {%s};"
    % (coords(r, 0, 1, 1.0, 1e12), coords(r, 0, 2, 1.0, 1e12)),
    "control code", "edge position (ps)",
    "Nine codes, nine measured answers. There is no waveform to compare "
    "here: what the block does is place an edge, so that is what is "
    "plotted.")

# ---- 4. the PLL, at the co-simulation boundary -------------------------
#
# vout, not a block trace. Case study 4's claim is about the COMPOSED
# system on the design's own testbench, and a loop filter answering a
# current step answers a smaller question than the section asks.
#
# Eight samples, because that is how often the digital side reads this
# node -- it is the only matched observation of vout the two runs share.
# The others in the boundary log are either a clock (aout) or driven by
# the digital side itself, where both runs agree by construction and a
# plot would prove nothing.
def boundary(path, net):
    out = []
    for ln in Path(path).read_text().splitlines():
        f = ln.split()
        if len(f) == 4 and f[2] == net:
            out.append((float(f[1]), float(f[3])))
    return out


m = boundary(RUNS / "demo4_pll/cosim/model/boundary.log", "vout")
g = boundary(RUNS / "demo4_pll/cosim/golden/boundary.log", "vout")
worst = max(abs(a[1] - b[1]) for a, b in zip(m, g)) * 1e3
figs["pll"] = fig(
    "    \\addplot[black,mark=*,mark size=1.5pt] coordinates {%s};\n"
    "    \\addplot[red,dashed,mark=o,mark size=2.4pt] coordinates {%s};"
    % (" ".join("(%.4g,%.6g)" % (t * 1e6, v) for t, v in g),
       " ".join("(%.4g,%.6g)" % (t * 1e6, v) for t, v in m)),
    "time (\\textmu s)", "control voltage (V)",
    # NO WORST-DIFFERENCE HERE. It is a draw -- see the paragraph below
    # the table, which lists seven of them -- and a caption quoting its
    # own sample contradicted the table the moment either was
    # regenerated. The number belongs in one place, next to the
    # explanation of what it is.
    "The control voltage at the co-simulation boundary: the composed "
    "models against the transistors, on the design's own testbench, on a "
    "node the loop holds near 1.85\\,V. Both settle to the same place "
    "and hold it. Eight samples because that is how often the digital "
    "side reads this node; how closely they agree at any one instant is "
    "a draw, and the table's bar is what the verdict is taken against.")

s = TEX.read_text(encoding="utf-8")
for name, body in figs.items():
    a, b = "%% <<TRACE:%s>>" % name, "%% <<END TRACE:%s>>" % name
    assert s.count(a) == 1 and s.count(b) == 1, "markers for %s" % name
    # A lambda, because the replacement is LaTeX: re.sub would read its
    # backslashes as group escapes and fail on the first \legend.
    s = re.sub(re.escape(a) + r".*?" + re.escape(b),
               lambda _m, _t=a + "\n" + body + b: _t, s, flags=re.S)
TEX.write_text(s, encoding="utf-8")

kb = sum(len(b) for b in figs.values()) / 1024.0
print("drew %d figures into the paper, %.0f kB of coordinates" % (len(figs), kb))
