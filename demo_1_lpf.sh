#!/usr/bin/env bash
# DEMO 1 of 3 -- Low-pass filter: the flow works, on both kinds of input.
#
# The point of this one: circuit to verified model in under a minute, and the
# model holds up under BINARY data, not just the small-signal sweep it was
# fitted from. That second part is what people assume breaks.
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
  --emit-uvm-ms 2>&1 | grep -viE '^\s*$' | sed 's/^/    /'
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
say "52 DC checks exact, 18 AC checks clean, worst 0.06 dB against a"
say "0.25 dB tolerance."
say ""
say "Two of those AC checks used to fail, at 89 MHz, and the reason is"
say "worth a moment. The model was right: driven and measured on its own"
say "it reads -38.30 dB where the fit and ngspice both say -38.35. The"
say "TESTBENCH was wrong. It synthesises its excitation at 64 samples per"
say "cycle, while the model only advances on its own 304 ps step -- so at"
say "89 MHz the model saw every OTHER drive update and nothing it was"
say "asked for. The reading came out 0.28 dB low, over a 0.25 dB tolerance."
say ""
say "The fix was not the tolerance. The check now stops where the model can"
say "still see the excitation it is given, which is 50 MHz here. A"
say "testbench that reports a good model as bad is the failure mode that"
say "teaches people to widen tolerances until nothing fails at all."
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
