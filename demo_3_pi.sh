#!/usr/bin/env bash
# DEMO 3 of 3 -- Phase interpolator: where the method reaches its edge.
#
# The point of this one: honesty. The measurement works and gives a real
# result -- full 500 ps traversal across 9 codes -- but the pipeline cannot
# model this block, and it is worth saying why precisely rather than
# hand-waving. Three inputs against a single-input flow, and the observable
# is phase, not amplitude.
#
# Ending a demo on a limitation is what makes the first two believable.
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

hr "3. Why the usual pipeline has nothing to say here"
say "A phase interpolator has one clock and SIXTEEN enables, and the"
say "characterisation flow fits a single-input Vout(Vin) into"
say "'module (input real in_val, output real out_val)'. There is nowhere to"
say "put the other sixteen."
say ""
say "The earlier analog-controlled version made it quantitative: the fit"
say "returned a small-signal gain of -0.03 into a 39 mV excursion. That is"
say "the pipeline saying there is no amplitude transfer function here."
say ""
say "It is right. There isn't one -- and that is the useful observation,"
say "not a dead end. The sixteen enables are not sixteen analog inputs:"
say "they carry a thermometer CODE, they only ever sit at one of two DC"
say "values, and what the block does with them is move its output edge."
say "Nine settings, one number each."
say ""
say "So the model is not H(s) at all. It is a delay line:"
say ""
say "      out(t) = in(t - delay[code])"
say ""
say "which is what a system-level simulation of a PI actually wants. Measure"
say "the phase at every code, and that table IS the model."
beat

hr "4. Phase against code"
say "Sweeping the thermometer code, measuring where the output edge lands."
echo
python3 "$HARNESS/demo_pi.py" 2>&1 | tail -26 | sed 's/^/    /'
beat

hr "5. From that table to a model that runs"
say "The nine numbers above are the model. Emitted as SystemVerilog and"
say "then SIMULATED -- comparing a model against the table it was built"
say "from would prove nothing, so this drives the generated module with a"
say "clock and asks where its output edge actually lands."
echo
python3 "$HARNESS/pi_model.py" 2>&1 | sed 's/^/  /'
beat

hr "6. How we know the residual is real"
say "Three mechanisms, each chosen from what the measurement said, and the"
say "first two rejected by it:"
say ""
say "  -4.71 LSB   analog control into a source-coupled pair"
say "              -- turned over inside ~40 mV: a switch, not a blend"
say "  -3.56 LSB   slowed the clock edges so both phases ramp at once"
say "              -- the jump spread over two codes instead of one"
say "  -1.61 LSB   thermometer-coded unit cells"
say "              -- linearity from matching, not from staying linear"
say ""
say "A metric that rejects two plausible fixes is one worth trusting."
beat

hr "Summary"
say "traversal    : -500.1 ps against a 500 ps I/Q separation -- the full span"
say "codes        : 9, monotonic, zero cycle-to-cycle jitter"
say "DNL / INL    : -1.61 / -1.59 LSB"
say ""
say "model        : code-selected delay line, 9 codes, generated and simulated"
say "               -- edge lands within 1.2 ps, under 2% of a 62.5 ps LSB"
say ""
say "Both of the gaps this demo used to end on are closed: a timing"
say "observable in the equivalence check (see the DCC demo), and a model for"
say "a block whose control is a code rather than an analog input."
say ""
say "What is still out of scope, precisely: two genuinely CONTINUOUS inputs."
say "This works by enumerating a finite set of discrete settings -- which is"
say "what makes it tractable, since thermometer coding turns 2^16"
say "combinations into nine. A 2-D surface is different work."
say ""
say "csv: $HOME/s2r_runs/demo_pi/phase_vs_code.csv"
echo
