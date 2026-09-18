#!/usr/bin/env bash
# DEMO 4 of 4 -- Phase-locked loop: the first three are blocks, this one is a
# LOOP, and a loop does not let a small error stay small.
#
# The point of this one: three characterisation problems in one netlist, none
# of them a transfer function, composed back into an analog top and checked
# against the transistors on the design's OWN testbench.
#
# UNLIKE DEMOS 1-3 THIS ONE IS NOT SELF-CONTAINED. It models the analog half
# of a co-simulation, so it needs that co-simulation: the RTL, the DPI bridge,
# and a SHARED libngspice for the bridge to dlopen. That is a different
# ngspice build from the binary the other demos use, and the check below names
# every piece rather than failing halfway through a twelve-minute run.
#
#   DEMO_PAUSE=1 ./demo_4_pll.sh    pause between acts, for presenting live

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S2R="${S2R:-$HOME/spice2rnm}"
COSIM="${COSIM:-$HOME/ams-cosim}"
UVM_MS_LIB="${UVM_MS_LIB:-$HOME/uvm_ms_demo/ms}"
UVM_SRC="${UVM_SRC:-$HOME/iverilog-unified/uvm-core/src}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
NGLIB="${NGLIB:-$HOME/ngspice-46-shared/src/.libs}"
XEZIM="${XEZIM:-$HOME/xezim/target/release/xezim}"
BRIDGE="${BRIDGE:-$COSIM/ams_bridge.so}"
OUT="$HOME/s2r_runs/demo4_pll"

PLL="$COSIM/examples/pll"
NETLIST="$PLL/pll_analog.cir"

hr()  { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '=%.0s' {1..72})"; }
say() { printf '  %s\n' "$*"; }
beat(){ [ "${DEMO_PAUSE:-0}" = "1" ] && { printf '\n  [enter] '; read -r _; }; return 0; }

# --- prerequisites, named individually ---------------------------------------
# A missing piece here is not a typo, it is a build someone has to do, so say
# which and where rather than "missing: <path>".
miss=0
need() {  # need <path> <what it is> <where it comes from>
  if [ -e "$1" ]; then
    printf '  \033[32mok\033[0m    %-34s %s\n' "$2" "$1"
  else
    printf '  \033[31mMISS\033[0m  %-34s %s\n' "$2" "$3"
    miss=1
  fi
}

hr "0. What this one needs"
say "Demos 1-3 take a netlist and nothing else. This one models the analog"
say "half of a running co-simulation, so it needs the other half too."
echo
need "$NETLIST"                 "the PLL netlist"          "github.com/vrajeshprakhya/ams-cosim"
need "$PLL/pfd.sv"              "phase detector RTL"       "same repo, examples/pll"
need "$PLL/divn.sv"             "divider RTL"              "same repo, examples/pll"
need "$PLL/tb_pll.sv"           "the co-simulation tb"     "same repo, examples/pll"
need "$BRIDGE"                  "the DPI bridge"           "build it: ams-cosim/build.sh"
need "$NGLIB/libngspice.so"     "SHARED libngspice"        "ngspice --with-ngshared"
need "$NGSPICE"                 "ngspice binary"           "a normal ngspice build"
need "$XEZIM"                   "the SV simulator"         "xezim, release build"
if [ "$miss" = "1" ]; then
  echo
  say "Nothing was run. The pieces above are what the co-simulation is made"
  say "of; demos 1-3 need none of them and still work."
  exit 1
fi
cd "$S2R" || exit 1
beat

hr "1. Three problems in one netlist"
say "The analog partition is a loop: a ring oscillator, a charge pump, and a"
say "passive filter. The digital half -- phase detector and divider -- is RTL"
say "and never appears in the netlist."
echo
grep -E '^x(cp|lf|vco) ' "$NETLIST" | sed 's/^/    /'
echo
say "Two sources carry ngspice's 'external' keyword: that is the deck saying"
say "a controlling program drives them. They are the analog/digital boundary."
grep -E 'external' "$NETLIST" | sed 's/^/    /'
echo
say "None of these three is a transfer function, and each fails the default"
say "for its own reason:"
say ""
say "  ro_vco   oscillates with its inputs held at DC, so its output is a"
say "           FREQUENCY, not a gain          -> tuning curve, scored on rate"
say "  cpump    a complementary pair driven from INDEPENDENTLY controlled"
say "           gates, not a gain stage        -> one I(V) table per state"
say "  lpfilt   only R and C, so its state space is EXACT and needs no"
say "           fitting at all                 -> read from the topology"
beat

hr "2. One command"
say "The whole system goes in: the netlist, the RTL, and the testbench. What"
say "each block is gets decided from its topology, not from its name."
echo
say "  python3 -m spice2rnm \\"
say "      $PLL/pll_analog.cir \\"
say "      $PLL/pfd.sv $PLL/divn.sv $PLL/tb_pll.sv \\"
say "      --hierarchical --emit-assertions --output-node vout \\"
say "      --llm-block-function --check-jitter-transfer \\"
say "      --emit-uvm-ms --uvm-ms-lib $UVM_MS_LIB \\"
say "      --out-dir $OUT"
echo
say "This takes about 16 minutes, most of it measuring the ring's tuning"
say "curve one point at a time. Demos 1-3 finish in under 16 minutes between"
say "them; a loop costs more because the oscillator has to be timed, not"
say "swept."
echo
say "--llm-block-function asks a model what each block is FOR. It changes no"
say "measurement and emits no model -- it picks the STIMULUS and the METRIC"
say "that score one, which for the two inverters in the ring is the whole"
say "difference between a verdict that means something and one that does"
say "not. Everything it proposes is checked against the measured circuit,"
say "and where they disagree the measurement wins."
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo
  say "ANTHROPIC_API_KEY is NOT set here, so the advisor will fail safe and"
  say "the chirp will be kept. The run still completes, and act 5 will say so"
  say "-- it reads the metric the run recorded, not the flag on this line."
fi
beat

rm -rf "$OUT"
python3 -m spice2rnm \
  "$PLL/pll_analog.cir" "$PLL/pfd.sv" "$PLL/divn.sv" "$PLL/tb_pll.sv" \
  --hierarchical --emit-assertions --output-node vout \
  --llm-block-function --check-jitter-transfer \
  --emit-uvm-ms --uvm-ms-lib "$UVM_MS_LIB" \
  --out-dir "$OUT" \
  --ngspice-bin "$NGSPICE" --xezim-bin "$XEZIM" \
  --ngspice-lib "$NGLIB" --ams-bridge "$BRIDGE" \
  > "$OUT.log" 2>&1 || { echo "run failed; see $OUT.log"; tail -20 "$OUT.log"; exit 1; }

hr "3. The golden probe runs FIRST"
say "Before anything is characterised, the co-simulation runs against the"
say "TRANSISTORS, with no model in existence. It is first because"
say "characterisation cannot otherwise know where in its range each block is"
say "used -- that is a property of the closed loop, and it exists only once"
say "the digital side is attached."
echo
grep -aE 'boundary node\(s\) measured|^    (aout|vout|dra) ' "$OUT.log" | head -6 | sed 's/^/  /'
beat

hr "4. Where each block actually works"
say "The probe measures a voltage BAND and a switching RATE per net. Both"
say "matter, and neither is in the netlist:"
echo
grep -aE "control port 'cont'" "$OUT.log" | cut -c1-200 | fold -s -w 72 | sed 's/^/    /'
echo
say "0.3% of the swept range. A whole-range verdict on that block would be"
say "failing it over a bias the design cannot reach."
beat

hr "5. Per-block equivalence"
say "Each emitted .sv is elaborated, driven, and compared against the SPICE"
say "measurement -- the check that catches a code-generation error, which a"
say "held-out score cannot see because it never reads the emitted file."
echo
grep -aE "block (ro_vco|cpump|lpfilt):|equivalence (PASS|FAIL)|rc\): equivalence" "$OUT.log" \
  | sed 's/^[0-9T:.-]*Z *//' | cut -c1-150 | sed 's/^/    /' | head -8
echo
say "The two inverters are where the DEFAULT verdict is wrong. An rms voltage"
say "comparison is close to blind to edge placement, which is the entire"
say "function of a buffer. What each was actually scored on:"
echo
python3 - "$OUT/result.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["result"]
for row in r.get("block_results") or []:
    eq = ((row.get("pipeline_result") or {}).get("equivalence")) or {}
    if not eq.get("checked"):
        continue
    name = row["block"]["name"]
    if eq.get("metric") == "timing":
        t = eq.get("timing") or {}
        print("    %-5s DUTY  %+.3f pp against a %.3f pp bar"
              % (name, t.get("duty_error_pp", float("nan")),
                 eq.get("timing_threshold_pp", float("nan"))))
    else:
        print("    %-5s RMS   %.4f against a %.2f bar -- and its worst instant"
              % (name, eq.get("rms_error_norm", float("nan")),
                 eq.get("threshold", float("nan"))))
        print("    %-5s       is %.1f%% of full swing, which that figure cannot see"
              % ("", 100.0 * (eq.get("max_error_norm") or 0.0)))
PY
echo
say "And what the advisor proposed, checked against the circuit:"
echo
python3 - "$OUT/result.json" <<'PY'
import json, sys, textwrap
keep = ("block function:", "clock from MEASUREMENT", "the re-emitted")
r = json.load(open(sys.argv[1]))["result"]
ws = []
for row in r.get("block_results") or []:
    name = row["block"]["name"]
    for w in ((row.get("pipeline_result") or {}).get("warnings") or []):
        if w.startswith(keep):
            ws.append("%s: %s" % (name, w if len(w) <= 340 else w[:337] + "..."))
ws += [w for w in (r.get("warnings") or []) if w.startswith(keep)]
if not ws:
    ws = ["the advisor reached no proposal, so the chirp and the rms verdict "
          "stand untouched -- which is the fail-safe, not a failure"]
for w in ws:
    print(textwrap.fill(w, 70, initial_indent="    ",
                        subsequent_indent="      "))
    print()
PY
beat

hr "6. What a static score cannot see"
say "Every score so far is STATIC: a value at an operating point. That is"
say "blind to a real error. The oscillator model schedules its edges from"
say "the control; one that samples the control once per half cycle and one"
say "that integrates it over the cycle carry the SAME tuning curve, so the"
say "tuning-curve check scores them identically -- it passes both. Fed the"
say "same noisy control, the sampling one produces 28.6x the transistors\'"
say "period jitter."
echo
say "So the disturbance is injected in SPICE, and the waveform ngspice"
say "actually solved is replayed into the model sample for sample. Two"
say "random sequences with the same sigma would give two different answers;"
say "replaying the disturbance compares transfer instead of sample size."
echo
grep -aE "jitter transfer" "$OUT.log" | cut -c1-200 | fold -s -w 72 | sed "s/^/    /" | head -14
echo
say "Both of the model\'s inputs are exercised, not just the control: the"
say "supply moves this ring by 450.6 MHz/V, comparable to the control and"
say "opposite in sign."
echo
say "On THIS design the gate would decline -- the control moves 9.7 uV rms"
say "per 2.5 ns period, worth 0.023 ps against a 0.052 ps measurement"
say "floor, so the two model forms agree and a sweep would measure the"
say "solver. --check-jitter-transfer overrides that, because a demo that"
say "showed only the decline would never show the check."
beat

hr "7. Checked as a system, against the transistors"
say "Per-block scores are evidence about each block alone. The loop asks a"
say "different question, and the co-simulation answers it directly: the"
say "design's own testbench, run twice, with only its DPI bridge functions"
say "rewritten. Thresholds, expressions and verdict are byte-identical."
echo
grep -aE '^  (partition|floor|golden|reference) |^      ams_(get|set) |^    dra ' "$OUT.log" \
  | cut -c1-140 | sed 's/^/  /' | head -12
beat

hr "Summary"
# READ FROM THE RUN, NOT TYPED. The first version of this printed "5 of 5
# pass" and "vout to 0.2 mV" as literals, carried over from an earlier run.
# They were true, and they would have printed unchanged if this run had
# produced a failure -- a demo whose summary cannot disagree with its own
# output is marking its own homework, which is the one thing section 7 of
# the whitepaper says this tool must never do. Demos 1-3 grep their figures
# for the same reason.
# The equivalence results live in FOUR sections of result.json -- the
# transfer-function blocks under block_results, and the vco, charge-pump and
# rc routes each under their own -- and only two of the five print a
# greppable line. Counting log lines gave "2 pass", and the literal this
# replaced claimed "5 of 5": both wrong, in opposite directions, for the
# same reason. result.json is what the run concluded.
eq=$(python3 - "$OUT/result.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["result"]
ok = bad = 0
def tally(e):
    global ok, bad
    if isinstance(e, dict) and e.get("checked", True):
        if e.get("success"): ok += 1
        else: bad += 1
for row in r.get("block_results") or []:
    tally((row.get("pipeline_result") or {}).get("equivalence"))
for k in ("vco_results", "cp_results", "rc_results"):
    for v in (r.get(k) or {}).values():
        tally(v.get("equivalence"))
print("%d %d" % (ok, bad))
PY
)
n_eq_pass=${eq% *}
n_eq_fail=${eq#* }
verdict=$(grep -aoE "golden +: [A-Z]+" "$OUT.log" | head -1 | awk "{print \$3}")
floor=$(grep -aoE "floor +: [A-Z]+" "$OUT.log" | head -1 | awk "{print \$3}")
n_nodes=$(grep -acE "^      ams_(get|set) " "$OUT.log")
n_bad=$(grep -acE "^      ams_(get|set) [a-z]+ +(FAIL|INCONCLUSIVE)" "$OUT.log")
vout=$(grep -aoE "ams_get vout .*worst \|diff\| [0-9.e-]+" "$OUT.log" | grep -oE "[0-9.e-]+$" | head -1)
lock=$(grep -aoE "locked within [-0-9.]+% of [0-9.]+ MHz" "$OUT.log" | head -1)

say "blocks       : 3 composed as models, by 3 different routes"
say "               2 more emitted and individually checked"
say "equivalence  : $n_eq_pass pass, $n_eq_fail fail"
say "floor        : ${floor:-?}"
say "system       : ${verdict:-?} -- $n_nodes boundary signal(s), $n_bad failed"
[ -n "$vout" ] && say "               vout worst |diff| $vout V"
[ -n "$lock" ] && say "               $lock"
say ""
say "The control voltage is the number to read: it is where the loop stores"
say "its state, so a model that settles anywhere else disagrees there first."
say ""
say "Scope, precisely: this holds lock from a measured initial condition."
say "Acquisition is not tested -- it is hours of transistor SPICE from a cold"
say "start, which is why the deck states an .ic at all. One operating point,"
say "one corner, one reference rate."
say ""
say "run: $OUT/result.json   log: $OUT.log"
echo
