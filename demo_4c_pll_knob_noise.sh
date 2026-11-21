#!/usr/bin/env bash
# DEMO 4c -- the same PLL as demo 4a, with the shake moved from the battery
# to the knob.
#
# Demo 4a puts its noise on the supply: the whole ring oscillator sits on a
# shaky rail. This one keeps the rail quiet and puts the noise where a real
# loop makes it: in the loop filter's resistors, whose thermal noise lands
# on the VCO's control voltage (its knob, node vout) from INSIDE the loop.
#
# The question: when the filter model carries that noise, do the generated
# models still behave like the transistors, closed around the design's own
# RTL testbench?
#
# Same prerequisites as demo 4a (the RTL, the DPI bridge, a SHARED
# libngspice). Shorter run: no UVM-MS environment and no block-function
# advisor, because neither is about noise.
#
#   DEMO_PAUSE=1 ./demo_4c_pll_knob_noise.sh    pause between acts

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S2R="${S2R:-$HOME/spice2rnm}"
COSIM="${COSIM:-$HOME/ams-cosim}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
NGLIB="${NGLIB:-$HOME/ngspice-46-shared/src/.libs}"
XEZIM="${XEZIM:-$HOME/xezim/target/release/xezim}"
BRIDGE="${BRIDGE:-$COSIM/ams_bridge.so}"
OUT="$HOME/s2r_runs/demo4c_knob"
PLL="$HOME/s2r_runs/demo4c_knob_deck"
PLL_SRC="${PLL_SRC:-$HERE/rtl/pll}"
DECK_SRC="$HERE/netlists/pll_analog_knob.cir"
# The testbench opens its deck by a fixed name, so the knob deck is copied
# in under that name. The file in netlists/ keeps its own.
NETLIST="$PLL/pll_analog.cir"

# START FROM EMPTY, guarded to this run directory, as demo 4a does.
for d in "$OUT" "$PLL"; do
  case "$d" in
    "$HOME"/s2r_runs/?*) rm -rf "$d" ;;
    *) echo "refusing to clean unexpected path: $d" >&2; exit 1 ;;
  esac
done
mkdir -p "$OUT" "$PLL"

hr()  { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '=%.0s' {1..72})"; }
say() { printf '  %s\n' "$*"; }
beat(){ [ "${DEMO_PAUSE:-0}" = "1" ] && { printf '\n  [enter] '; read -r _; }; return 0; }

miss=0
need() {
  if [ -e "$1" ]; then
    printf '  \033[32mok\033[0m    %-34s %s\n' "$2" "$1"
  else
    printf '  \033[31mMISS\033[0m  %-34s %s\n' "$2" "$3"
    miss=1
  fi
}

hr "0. What this one needs"
need "$DECK_SRC"                "the knob-noise PLL deck"  "this repo, netlists/"
need "$PLL_SRC/pfd.sv"          "phase detector RTL"       "this repo, rtl/pll/"
need "$PLL_SRC/divn.sv"         "divider RTL"              "this repo, rtl/pll/"
need "$PLL_SRC/tb_pll.sv"       "the co-simulation tb"     "this repo, rtl/pll/"
need "$BRIDGE"                  "the DPI bridge"           "build it: ams-cosim/build.sh"
need "$NGLIB/libngspice.so"     "SHARED libngspice"        "ngspice --with-ngshared"
need "$NGSPICE"                 "ngspice binary"           "a normal ngspice build"
need "$XEZIM"                   "the SV simulator"         "xezim, release build"
if [ "$miss" = "1" ]; then
  echo
  say "Nothing was run. Demos 1-3 need none of the pieces above."
  exit 1
fi

cp "$PLL_SRC/pfd.sv" "$PLL_SRC/divn.sv" "$PLL_SRC/tb_pll.sv" "$PLL/"
cp "$DECK_SRC" "$NETLIST"
# ASSERTED, not assumed: three noise cards in the filter, and a quiet rail.
# A deck without them would leave every line below describing a shake that
# is not in the circuit.
n_knob=$(grep -cE '^Vn[123] .* trnoise\(' "$NETLIST")
if [ "$n_knob" != "3" ] || ! grep -qE '^vdd dd 0 dc \{vcc\}$' "$NETLIST"; then
  echo
  say "netlists/pll_analog_knob.cir is not the deck this demo describes"
  say "(expected 3 noise cards Vn1..Vn3 in lpfilt and a quiet 'vdd dd 0 dc"
  say "{vcc}'; found $n_knob noise card(s)). Nothing was run."
  exit 1
fi
cd "$S2R" || exit 1
beat

hr "1. Where the knob shakes"
say "A PLL steers its oscillator with a voltage: the knob. A charge pump"
say "squirts current into a loop filter (resistors and capacitors), and the"
say "filter smooths those squirts into the knob voltage, vout."
echo
say "Every resistor shakes a little on its own: thermal noise, sqrt(4kTR)."
say "In the deck each one gets that noise as a small random voltage in series"
say "with it, redrawn every 100 ps:"
echo
grep -E '^(R[123]|Vn[123]) ' "$NETLIST" | sed 's/^/    /'
echo
say "These are 1000x the resistors' real thermal noise, ON PURPOSE. At the"
say "real size the knob moves about 2.9 uV rms (sqrt(kT/C3)), far too small"
say "for any run here to see. This is a stress case, labelled as one."
say "The supply is quiet in this deck, so any shake comes from the knob."
beat

hr "2. One command"
say "  python3 -m spice2rnm $NETLIST \\"
say "      $PLL/pfd.sv $PLL/divn.sv $PLL/tb_pll.sv \\"
say "      --hierarchical --emit-assertions --out-dir $OUT"
echo
say "About 12 minutes, most of it timing the ring oscillator."
python3 -m spice2rnm \
  "$NETLIST" "$PLL/pfd.sv" "$PLL/divn.sv" "$PLL/tb_pll.sv" \
  --hierarchical --emit-assertions \
  --out-dir "$OUT" \
  --ngspice-bin "$NGSPICE" --xezim-bin "$XEZIM" \
  --ngspice-lib "$NGLIB" --ams-bridge "$BRIDGE" \
  > "$OUT.log" 2>&1 || { echo "run failed; see $OUT.log"; tail -20 "$OUT.log"; exit 1; }
beat

hr "3. The filter model carries the shake"
say "The filter is only resistors and capacitors, so its model is exact, read"
say "off the circuit with nothing fitted. Each noise source becomes one more"
say "input to that model, with its own seeded random generator:"
echo
grep -aE "block 'lpfilt' \(rc\): noise input\(s\) carried" "$OUT.log" \
  | sed 's/^warning: //' | fold -s -w 70 | sed 's/^/    /'
echo
say "Then each source is checked on its own: the model's exact random draws"
say "are fed into SPICE, and the two outputs are compared step by step."
echo
grep -aE "block 'lpfilt' \(rc\): (equivalence|noise input [A-Za-z0-9_]+ )" "$OUT.log" \
  | sed 's/^warning: //' | fold -s -w 70 | sed 's/^/    /'
echo
say "One source is NOT CHECKED, and that is physics, not a gap. The pump"
say "pushes a set current through R1, so a voltage in series with R1 cannot"
say "change how much charge reaches the capacitors. It only shakes the pump's"
say "own node, dra. The knob never sees it, so there is nothing to compare."
beat

hr "4. Checked as a system, against the transistors"
say "The design's own testbench, run twice: once on the transistors, once on"
say "the generated models. Both runs shake, but with DIFFERENT random draws,"
say "so they are compared on behaviour, not sample by sample:"
echo
grep -aE "this deck declares transient noise on" "$OUT.log" | head -1 \
  | sed 's/^ *//' | fold -s -w 70 | sed 's/^/    /'
echo
grep -aE '^  (floor|golden) |^  wall clock: |^      ams_(get|set) ' "$OUT.log" \
  | cut -c1-140 | sed 's/^/  /' | head -10
echo
say "How to read a noisy comparison: the transistors are run TWICE (the"
say "probe, then the golden), and with different random draws they do not"
say "agree with themselves either. The models should land inside that spread."
echo
python3 - "$OUT.log" <<'PY'
import re, sys
log = open(sys.argv[1], errors="replace").read()
who = ["transistors, probe run ", "models                 ",
       "transistors, golden run"]
v = re.findall(r"locked within [-0-9.]+% of ([0-9.]+) MHz at ([0-9.]+) V", log)
for name, (f, vc) in zip(who, v):
    print("    %s  %s MHz, knob settles at %s V" % (name, f, vc))
if len(v) == 3:
    t1, m, t2 = (float(x[1]) for x in v)
    lo, hi = min(t1, t2), max(t1, t2)
    print()
    print("    the two transistor runs differ by %.1f mV from noise alone;"
          % ((hi - lo) * 1e3))
    print("    the models are %s that spread"
          % ("INSIDE" if lo <= m <= hi else
             "%.1f mV OUTSIDE" % (1e3 * min(abs(m - lo), abs(m - hi)))))
m = re.search(r"^    vout +[0-9.]+ \.\. +[0-9.]+ V +settled +([0-9.]+) \.\. +([0-9.]+) V",
              log, re.M)
if m:
    a, b = float(m.group(1)), float(m.group(2))
    print("    and the knob's settled band in the transistors is %.1f mV wide"
          % ((b - a) * 1e3))
PY
beat

hr "Summary"
# READ FROM THE RUN, NOT TYPED, as demo 4a does: a summary that cannot
# disagree with its own run is marking its own homework.
python3 - "$OUT/result.json" "$OUT.log" <<'PY'
import json, re, sys
r = json.load(open(sys.argv[1]))["result"]
log = open(sys.argv[2], errors="replace").read()
rc = (r.get("rc_results") or {}).get("lpfilt") or {}
eq = rc.get("equivalence") or {}
noise = eq.get("noise") or []
print("  filter model : %d noise input(s) carried"
      % len(rc.get("noise") or []))
if eq.get("checked"):
    print("  filter check : %s, step test %.3f%% of its excursion"
          % ("PASS" if eq.get("success") else "FAIL", eq.get("worst_pct")))
for n in noise:
    if n.get("checked"):
        print("    %-4s %s  %.3f%% worst over %d draws"
              % (n["source"], "PASS" if n.get("success") else "FAIL",
                 n.get("worst_pct"), n.get("n_draws")))
    elif n.get("reaches_output") is False:
        land = re.findall(r"voltage at ('[^']+')", n.get("note") or "")
        print("    %-4s NOT CHECKED: never reaches the knob%s"
              % (n["source"], ", only shakes %s" % land[0] if land else ""))
    else:
        print("    %-4s NOT CHECKED: %s" % (n["source"],
              "; ".join(n.get("errors") or []) or "no reason recorded"))
m = re.search(r"golden +: ([A-Z]+)", log)
print("  system       : %s against the transistors" % (m.group(1) if m else "?"))
m = re.search(r"ams_get vout .*?worst \|diff\| ([0-9.e-]+)", log)
if m:
    print("                 vout worst |diff| %s V" % m.group(1))
v = re.findall(r"locked within [-0-9.]+% of ([0-9.]+) MHz", log)
if v:
    print("                 all %d runs locked at %s MHz" % (len(v), "/".join(sorted(set(v)))))
m = re.search(r"wall clock: ([^\n]+)", log)
if m:
    print("  speed        : " + m.group(1)[:90])
PY
echo
say "Scope, precisely: one stress level (1000x thermal), one operating point,"
say "holding lock from a measured .ic. The noise is white; 1/f noise is not"
say "carried and the tool refuses it by name. The models are judged on"
say "behaviour, because the two runs draw different random numbers."
say ""
say "run: $OUT/result.json   log: $OUT.log"
echo
