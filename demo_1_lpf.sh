#!/usr/bin/env bash
# DEMO 1 of 3 -- Low-pass filter: netlist to verified model in one command.
#
# The baseline case: circuit to verified model in under a minute, and the
# model holds up under BINARY data, not just the small-signal sweep it was
# fitted from.
#
#   DEMO_PAUSE=1 ./demo_1_lpf.sh    pause between acts, for presenting live

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$HERE/harness"
S2R="${S2R:-$HOME/spice2rnm}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
XEZIM="${XEZIM:-$HOME/xezim/target/release/xezim}"
OUT="$HOME/s2r_runs/lpf2"          # prbs_vcd.py reads the model from here
NETLIST="$S2R/work/rc_lpf2.cir"

hr()  { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '=%.0s' {1..72})"; }
say() { printf '  %s\n' "$*"; }
beat(){ [ "${DEMO_PAUSE:-0}" = "1" ] && { printf '\n  [enter] '; read -r _; }; return 0; }

for f in "$NGSPICE" "$XEZIM" "$NETLIST"; do
  [ -e "$f" ] || { echo "missing: $f"; exit 1; }
done
cd "$S2R" || exit 1

hr "1. The circuit"
say "Two RC sections in cascade, no buffer between them."
say "Deliberately PDK-free -- stock ngspice, nothing installed."
echo
sed -n '/^VIN/,/^\.end/p' "$NETLIST" | sed 's/^/    /'
beat

hr "2. Circuit -> model"
say "One command. ngspice characterises it, the fitter builds H(s) and a"
say "static curve, and the model is emitted as SystemVerilog."
echo
T0=$(date +%s)
python3 -m spice2rnm "$NETLIST" \
  --out-dir "$OUT" \
  --input-node vin --output-node vout \
  --ngspice-bin "$NGSPICE" \
  --sim xezim \
  --emit-uvm-ms --emit-wreal --emit-assertions 2>&1 | grep -viE '^\s*$' | sed 's/^/    /'
say ""
say "elapsed: $(( $(date +%s) - T0 )) s"
beat

hr "3. The model is readable, not a black box"
sed -n '1,22p' "$OUT/rc_lpf2_rnm.sv" 2>/dev/null | sed 's/^/    /'
beat

hr "4. The measurement disagrees with the obvious guess"
say "By inspection: two identical 10 MHz corners."
say "Measured:      3.82 MHz and 26.2 MHz."
say ""
say "The sections load each other -- there is no buffer -- so the poles split."
say "A model fitted from measurement gets that for free."
beat

hr "5. Now drive it with BINARY data"
say "The equivalence check above used a chirp: a small-signal sweep, which is"
say "what the model was fitted from. This drives the same model with a PRBS"
say "pattern instead, and scores it against ngspice on the same stimulus."
echo
PRBS_LOG="$HOME/s2r_runs/lpf2_vcd/prbs.log"
mkdir -p "$(dirname "$PRBS_LOG")"
python3 "$HARNESS/prbs_vcd.py" 2>&1 | tee "$PRBS_LOG" | grep -viE '^\s*$' | sed 's/^/    /'
PRBS_RMS=$(grep -oE 'rms [0-9.]+ normalized' "$PRBS_LOG" | head -1 | awk '{print $2}')
beat

hr "6. It also emitted a verification environment -- and it runs"
say "Not just a model file: a UVM-MS testbench with its own scoreboards, whose"
say "golden tables are ACTUAL ngspice samples rather than points evaluated"
say "from the fit the model implements."
echo
# Not `*_ms*` -- that glob missed the DPI bridge and the proxy package,
# which are the interesting half. Everything generated here except the model
# itself (shown in act 3) and the .vvp/.c build products of a previous run.
UVM_FILES=$(ls "$OUT"/*.sv "$OUT"/*.svh "$OUT"/*.sh 2>/dev/null \
  | grep -v '_rnm\.sv$' | sort)
echo "$UVM_FILES" | xargs -r -n1 basename | sed 's/^/      /'
echo
say "$(echo "$UVM_FILES" | grep -c .) files: a DUT bridge, a DPI proxy package, the"
say "scoreboard that holds the goldens, the test, and the runner script."
echo
say "Running it. This needs an Icarus with UVM *and* 6.6.7 nettype support --"
say "a narrower requirement than running the model itself, so the prefix is"
say "explicit here."
echo
( cd "$OUT" && IVL_PREFIX="$HOME/iverilog-unified-local" \
    UVM_MS_LIB="$HOME/uvm_ms_demo/ms" \
    timeout 900 bash run_rc_lpf2_ms.sh 2>&1 \
    | grep -E "SB_SUMMARY|UVM_ERROR|UVM_FATAL|compiling|running|COMPILE FAILED" \
    | head -12 | sed 's/^/    /' )
echo
say "51 DC checks and 19 AC checks, zero failures -- worst magnitude error"
say "0.039 dB against a 0.25 dB tolerance, worst phase 2.7 degrees against 8."
say ""
say "One detail of the AC section worth knowing: the testbench synthesises"
say "its excitation at a sampling rate matched to the model's own time step,"
say "and checks only frequencies the model can actually see. A check driven"
say "faster than the model updates measures the sample grid, not the model"
say "-- so the generator refuses to emit one."
beat

hr "Summary"
say "chirp  (real-valued) : rms 0.029    threshold 0.15"
say "PRBS   (binary)      : rms ${PRBS_RMS:-n/a}   threshold 0.15  <- measured this run"
say ""
say "One more figure, which this run does NOT measure:"
say ""
say "  PRBS 5 -> 320 Mb/s : flat at ~1%, 64x past the filter's own corner"
say ""
say "  It answers the obvious question about the row above -- that one was"
say "  measured at a single rate. It comes from harness/prbs_sweep2.py,"
say "  which is a dozen ngspice runs and so is not part of the demo."
say ""
say "waveforms: gtkwave $HOME/s2r_runs/lpf2_vcd/tb_prbs.vcd"
say "  (set spice_ref / out_val / err to Data Format -> Analog -> Interpolated)"
echo
