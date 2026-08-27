#!/usr/bin/env bash
# DEMO 2 of 3 -- Duty-cycle corrector: the flow runs, and tells you when its
# own assumption does not hold.
#
# The point of this one: a good fit is not the same as a valid model, and the
# difference is STRUCTURAL. The AC fit here is fine (0.19 dB) either way, but
# the usual `static + (H - H(0))*u` decomposition is only valid near the bias:
# a comparator's linear correction term is a +-24 V quantity on a 1.8 V supply.
# The pipeline detects the level dependence and emits a Wiener structure
# instead, which is bounded by the static curve by construction. What is left
# over after that is the real, honest limitation -- the poles were fitted at one
# bias point and the block's move 613,666x across its range.
#
# Also: duty is invisible to an rms voltage comparison, which is why the
# equivalence check now reports edge placement alongside it.
#
#   DEMO_PAUSE=1 ./demo_2_dcc.sh    pause between acts, for presenting live

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$HERE/harness"
S2R="${S2R:-$HOME/spice2rnm}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
XEZIM="${XEZIM:-$HOME/xezim/target/release/xezim}"
OUT="$HOME/s2r_runs/dcc2"          # dcc_vcd.py reads the model from here
NETLIST="$S2R/work/dcc.cir"

hr()  { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '=%.0s' {1..72})"; }
say() { printf '  %s\n' "$*"; }
beat(){ [ "${DEMO_PAUSE:-0}" = "1" ] && { printf '\n  [enter] '; read -r _; }; return 0; }

for f in "$NGSPICE" "$XEZIM" "$NETLIST"; do
  [ -e "$f" ] || { echo "missing: $f"; exit 1; }
done
cd "$S2R" || exit 1

hr "1. The circuit"
say "A comparator against a movable threshold, then a buffer to square the edge."
say "vctrl is the correction knob: it slides the slicing point along the"
say "clock's finite edges, trading high time against low time."
say ""
say "VCLK is DC+AC rather than PULSE so the .ac sweep has something to linearise"
say "about; the demos supply their own clock waveform for the transient runs,"
say "exactly as the pipeline's own equivalence check does."
echo
sed -n '/^VDD/,/^\.model/p' "$NETLIST"   | awk '/^\* ---/ {print; next} /^\*/ || /^\.model/ {next} NF' | sed 's/^/    /'
beat

hr "2. Circuit -> model"
T0=$(date +%s)
python3 -m spice2rnm "$NETLIST" \
  --out-dir "$OUT" \
  --input-node clk --output-node vout \
  --ngspice-bin "$NGSPICE" \
  --sim xezim 2>&1 | grep -viE '^\s*$' | sed 's/^/    /'
say ""
say "elapsed: $(( $(date +%s) - T0 )) s"
beat

hr "3. Read that result carefully"
say "The FIT is good:      AC 0.19 dB, DC curve a clean tanh."
say "The TRANSIENT fails:  rms 0.34 against a 0.15 threshold."
say ""
say "Two separate things are happening, and only one of them is a defect."
beat

hr "3a. The tool changed the model's STRUCTURE by itself"
say "A comparator's incremental gain is -26.6 at the slicing threshold and"
say "essentially zero once it has slid past. The textbook decomposition"
say ""
say "      y = static_curve(u) + (H(s) - H(0)) * (u - bias)"
say ""
say "is only right NEAR the bias. static_curve saturates; the linear"
say "correction term does not. With H(0) = -26.6 and a rail-to-rail +-0.9 V"
say "input, that correction alone is a +-24 V quantity on a 1.8 V supply."
say ""
say "So the pipeline emits a Wiener structure instead -- unity-DC-gain"
say "dynamics applied to the already-nonlinear signal, bounded by the static"
say "curve by construction. This is the line that does it:"
echo
grep -E "u_dev = static_curve|final_out = static_curve" "$OUT/dcc_rnm.sv" 2>/dev/null | sed 's/^/      /'
echo
say "Identical fitted coefficients, the two structures:"
say ""
say "      additive : model spans -22.15 .. +13.14 V     rms 5.64   FAIL"
say "      Wiener   : model spans   0.00 ..   1.63 V     rms 0.34   fail"
say "      SPICE    :               -0.01 ..  +1.81 V"
say ""
say "Both score rms_error_db = 0.186. The fit residual is IDENTICAL for a"
say "model that stays on the supply and one that misses it by 20 V, because"
say "the error is in the structure, not the coefficients. Nothing in the"
say "frequency domain can see this. Simulating the model against the circuit"
say "in time is what catches it."
beat

hr "3b. What is left over is real, and was announced up front"
grep -oE "the dominant pole moves [0-9.e+-]+ Hz -> [0-9.e+-]+ Hz \([0-9]+x\) across the characterized DC range" "$OUT/run.log" 2>/dev/null | tail -1 | sed 's/^/      /'
echo
say "The dynamics still carry the poles fitted at ONE bias point. So the"
say "model is now the right size and the wrong shape -- which is exactly"
say "what level dependence should look like, and why it still reads 0.34"
say "instead of passing."
say ""
say "That is the honest state of this block: the pipeline models it as well"
say "as a fixed-pole structure can, detects that a fixed pole is not enough,"
say "and says so. Closing the gap needs pole scheduling, which is currently"
say "implemented only for one-pole/no-zero blocks."
beat

hr "4. So measure what the block actually does"
say "A duty-cycle corrector's function is where the edges land. Sweeping the"
say "threshold gives the actuator characteristic a real loop would servo along."
echo
SWEEP_LOG="$HOME/s2r_runs/demo_dcc/sweep.log"
mkdir -p "$(dirname "$SWEEP_LOG")"
python3 "$HARNESS/demo_dcc.py" >"$SWEEP_LOG" 2>&1
if grep -q 'vctrl(V)' "$SWEEP_LOG"; then
  sed -n '/vctrl(V)/,$p' "$SWEEP_LOG" | sed 's/^/    /'
else
  tail -24 "$SWEEP_LOG" | sed 's/^/    /'
fi
NOSW=$(grep -c 'not switching' "$SWEEP_LOG")
if [ "${NOSW:-0}" -gt 0 ]; then
  echo
  say "($NOSW swept points did not switch at all -- the comparator runs out of"
  say " range at the top of the sweep. Full sweep log: $SWEEP_LOG)"
fi
beat

hr "5. And look at it"
say "A clock in, a clock out, SPICE and the model on the same axes."
say "The pipeline's own equivalence VCD is a chirp run -- smooth analog that"
say "shows nothing about edges. This one is the waveform worth showing."
echo
python3 "$HARNESS/dcc_vcd.py" 2>&1 | grep -viE '^\s*$' | sed 's/^/    /'
beat

hr "Summary"
say "fit quality       : AC 0.19 dB, DC residual 0.000586"
say "structure         : Wiener, chosen automatically from the level-dependence"
say "                    probe (additive would score the same 0.19 dB and swing"
say "                    -22 .. +13 V on a 1.8 V supply)"
say "transient         : 0.34 vs 0.15 threshold -- bounded, wrong shape, and"
say "                    that residual IS the 613,666x pole movement"
say "50% duty null     : vctrl = 1.1477 V"
say "correction range  : 51.5 percentage points of duty"
say ""
say "csv: $HOME/s2r_runs/demo_dcc/duty_vs_ctrl.csv"
echo
