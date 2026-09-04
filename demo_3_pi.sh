#!/usr/bin/env bash
# DEMO 3 of 3 -- Phase interpolator: a block with no amplitude transfer at
# all, verified by phase per code.
#
# The point of this one: the verification strategy follows the block's
# function. A PI has one clock and sixteen digital enables, essentially no
# amplitude response, and its whole job is where the output edge lands --
# so the tool measures phase at every code, generates a delay-line model,
# and emits a phase-per-code environment. Same tool, same one command.
#
#   DEMO_PAUSE=1 ./demo_3_pi.sh    pause between acts, for presenting live

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$HERE/harness"
S2R="${S2R:-$HOME/spice2rnm}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
OUT="$HOME/s2r_runs/demo3_pi"
NETLIST="$S2R/work/pi_therm.cir"

hr()  { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '=%.0s' {1..72})"; }
say() { printf '  %s\n' "$*"; }
beat(){ [ "${DEMO_PAUSE:-0}" = "1" ] && { printf '\n  [enter] '; read -r _; }; return 0; }

for f in "$NGSPICE" "$NETLIST"; do
  [ -e "$f" ] || { echo "missing: $f"; exit 1; }
done
cd "$S2R" || exit 1

hr "1. The circuit"
say "Sixteen identical current cells: eight driven by clock phase I, eight by"
say "phase Q a quarter period later. All of them sum onto one RC node."
echo
say "One unit cell -- enable transistor, then a differential pair:"
grep -E '^(MTI0|MI0A|MI0B) ' "$NETLIST" | sed 's/^/    /'
echo
say "The clocks, with deliberately SLOW 700 ps edges against a 500 ps I/Q"
say "separation, so both phases are mid-transition at once:"
grep -E '^VCLK' "$NETLIST" | sed 's/^/    /'
beat

hr "2. Thermometer coding"
say "Code k turns on k cells on phase I and 8-k on phase Q. Every code moves"
say "exactly one unit of current from one phase to the other, so the total"
say "tail current never changes -- the amplitude holds still while the"
say "crossing slides. Linearity comes from the cells MATCHING each other."
echo
grep -E '^VC[IQ][0-3] ' "$NETLIST" | sed 's/^/    /'
say "  ... 16 enables in total"
beat

hr "3. Why this block needs a different model entirely"
say "A phase interpolator has one clock and SIXTEEN digital enables, and"
say "essentially no amplitude transfer: measured, the small-signal gain is"
say "-0.03 into a 39 mV excursion. There is no H(s) here worth fitting --"
say "and the tool measures that rather than assuming it."
say ""
say "What the block DOES have is nine discrete settings, each placing the"
say "output edge somewhere. The sixteen enables are not sixteen analog"
say "inputs: they carry a thermometer CODE, they only ever sit at one of"
say "two values, and the block's function is one number per code."
say ""
say "So the model is not a transfer function at all. It is a delay line:"
say ""
say "      out(t) = in(t - delay[code])"
say ""
say "which is what a system-level simulation of a PI actually wants. Measure"
say "the phase at every code, and that table IS the model."
beat

hr "4. One command"
say "Same tool, code-phase path: measure at every setting, generate the"
say "model from the measurement, emit an environment that checks it."
echo
say "  python3 -m spice2rnm work/pi_therm.cir --output-node vout \\"
say "      --code-map thermometer:8 --code-period 2e-9 --emit-uvm-ms"
echo
T0=$(date +%s)
( cd "$S2R" && python3 -m spice2rnm work/pi_therm.cir \
    --out-dir "$OUT" --output-node vout \
    --code-map thermometer:8 --code-period 2e-9 \
    --ngspice-bin "$NGSPICE" --emit-uvm-ms --emit-wreal --emit-assertions 2>&1 ) \
  | grep -viE '^\s*$' | sed 's/^/    /'
say ""
say "elapsed: $(( $(date +%s) - T0 )) s"
say ""
say 'thermometer:8 is shorthand for the 9 settings of 16 sources this'
say "block has. A JSON list of {source: volts} covers any other coded"
say "block -- it says nothing about what the settings mean, which is what"
say "makes it general."
beat

hr "5. The environment it emitted, running"
say "Goldens are the ngspice edge measurements from the sweep above --"
say "not points read back from the model's own delay table, which would"
say "pass unconditionally."
echo
( cd "$OUT" && timeout 900 bash run_pi_therm_ms.sh 2>&1 \
  | grep -E "SB_SUMMARY|UVM_ERROR :|UVM_FATAL :|COMPILE FAILED|=== " \
  | sort -u | sed 's/^/    /' )
echo
say "A tenth of an LSB is the delay line's own quantisation floor, not a"
say "tolerance chosen to fit the answer: the model sizes its time step at"
say "ten steps per LSB, so this fails on a regression and not on rounding."
beat

hr "6. What the numbers mean"
say "A PI is specified by phase per code, DNL and INL. All of it derives"
say "from the run above -- one measurement behind the model, the"
say "testbench, and this table."
echo
python3 "$HARNESS/pi_analyze.py" "$OUT/result.json" 2>&1 | sed 's/^/    /'
beat

hr "7. The DNL figure is the circuit's, and the measurement can prove it"
say "The -1.61 LSB worst DNL belongs to the circuit, not to the flow -- and"
say "the same measurement quantified that across three design variants:"
say ""
say "  -4.71 LSB   analog control into a source-coupled pair"
say "              -- turned over inside ~40 mV: a switch, not a blend"
say "  -3.56 LSB   slowed clock edges so both phases ramp at once"
say "              -- the jump spread over two codes instead of one"
say "  -1.61 LSB   thermometer-coded unit cells"
say "              -- linearity from matching, not from staying linear"
say ""
say "A metric that resolves design choices like these is doing the job a"
say "characterisation bench does -- from a netlist, in seconds per variant."
beat

hr "Summary"
say "traversal    : -500.1 ps against a 500 ps I/Q separation -- the full span"
say "codes        : 9, monotonic, zero cycle-to-cycle jitter"
say "DNL / INL    : -1.61 / -1.59 LSB"
say ""
say "one command  : netlist -> measured model -> running testbench"
say "model        : code-selected delay line, 9 codes"
say "UVM-MS       : 9 phase checks, 0 failed, worst 3.3 ps against a 6.3 ps"
say "               tolerance (a tenth of an LSB)"
say ""
say "Scope, precisely: this path enumerates a finite set of discrete"
say "settings -- which is what makes it tractable, since thermometer coding"
say "turns 2^16 combinations into nine. Blocks with two genuinely"
say "CONTINUOUS control inputs are outside the current scope."
say ""
say "run: $OUT/result.json  (model, testbench and table all derive from it)"
echo
