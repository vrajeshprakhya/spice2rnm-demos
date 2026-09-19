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


def two(a, b):
    return ("    \\addplot[black] coordinates {%s};\n"
            "    \\addplot[red,dashed] coordinates {%s};" % (a, b))


figs = {}

# ---- 1. two-pole filter: smooth, so even sampling is honest ------------
r = read_csv(RUNS / "lpf2/equivalence/waveform_compare.csv",
             ["time_s", "spice_out", "sv_out"])
d = even(r, 200)
figs["lpf2"] = fig(
    two(coords(d, 0, 1, 1e6), coords(d, 0, 2, 1e6)),
    "time (\\textmu s)", "output (V)",
    "The model against the transistors over the whole transient. "
    "The two traces are drawn from \\texttt{waveform\\_compare.csv} in "
    "that run's own \\texttt{equivalence/} directory.")

# ---- 2. duty corrector: a clock, so a window at native rate ------------
r = read_csv(RUNS / "dcc2/equivalence/waveform_compare.csv",
             ["time_s", "spice_out", "sv_out"])
span = r[-1][0] - r[0][0]
t0 = r[0][0] + 0.55 * span
w = [x for x in r if t0 <= x[0] <= t0 + 0.012 * span]
figs["dcc2"] = fig(
    two(coords(w, 0, 1, 1e9), coords(w, 0, 2, 1e9)),
    "time (ns)", "output (V)",
    "A few cycles at the simulator's own resolution rather than the whole "
    "run decimated: sampling a square wave evenly would alias its edges "
    "and draw a waveform neither simulator produced.")

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

# ---- 4. PLL loop filter, driven by its charge pump ---------------------
r = read_csv(RUNS / "demo4_pll/lpfilt/equivalence/rc_compare.csv",
             ["time_s", "spice_out", "sv_out"])
d = even(r, 200)
figs["pll"] = fig(
    two(coords(d, 0, 1, 1e6), coords(d, 0, 2, 1e6)),
    "time (\\textmu s)", "control voltage (V)",
    "The loop filter's response to a current step from the charge pump. "
    "This is the node the loop stores its state on, so a model that "
    "settles elsewhere disagrees here first.")

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
