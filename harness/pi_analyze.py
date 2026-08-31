#!/usr/bin/env python3
"""The specification view of a code sweep, read from the pipeline's own run.

A phase interpolator is specified by phase per code, DNL and INL. The
pipeline measures the phases and reports traversal, LSB and monotonicity;
this derives the rest from result.json rather than sweeping again, so every
number on the slide comes from the one measurement that also produced the
model and its testbench.

demos/harness/demo_pi.py is the independent implementation the pipeline's
measurement was checked against -- both give -500.1 ps traversal and
-1.61 LSB DNL. It is kept for that cross-check, not called here.
"""
import json
import sys
from pathlib import Path

RESULT = Path(sys.argv[1] if len(sys.argv) > 1
              else Path.home() / "s2r_runs/demo3_pi/result.json")

if not RESULT.exists():
    print("  no run at %s" % RESULT)
    raise SystemExit(1)

d = json.loads(RESULT.read_text())
r = d.get("result", d)
rows = r.get("phases") or []
if len(rows) < 3:
    print("  only %d settings in %s" % (len(rows), RESULT))
    raise SystemExit(1)

print("  code   phase(ps)   step(ps)   swing(mV)   jitter(ps)")
print("  " + "-" * 54)
prev = None
steps = []
for entry in rows:
    code, ph = int(entry[0]), float(entry[1])
    sw = float(entry[2]) if len(entry) > 2 else float("nan")
    ji = float(entry[3]) if len(entry) > 3 else float("nan")
    step = "" if prev is None else "%8.1f" % ((ph - prev) * 1e12)
    if prev is not None:
        steps.append((ph - prev) * 1e12)
    print("  %4d   %8.1f  %9s   %9.1f   %10.2f"
          % (code, ph * 1e12, step, sw * 1e3, ji * 1e12))
    prev = ph

total = (float(rows[-1][1]) - float(rows[0][1])) * 1e12
ideal = total / len(steps)
inl, acc = [], 0.0
for st in steps:
    acc += st - ideal
    inl.append(acc)
dnl = max(steps, key=lambda x: abs(x - ideal)) - ideal
swings = [float(e[2]) for e in rows if len(e) > 2]

print()
print("  total phase moved : %+.1f ps" % total)
print("  mean step (1 LSB) : %+.1f ps" % ideal)
print("  DNL worst         : %+.1f ps  (%+.2f LSB)" % (dnl, dnl / abs(ideal)))
print("  INL worst         : %+.1f ps  (%+.2f LSB)"
      % (max(inl, key=abs), max(inl, key=abs) / abs(ideal)))
if swings:
    print("  swing variation   : %.1f mV  <- constant tail current should "
          "keep this small" % ((max(swings) - min(swings)) * 1e3))
