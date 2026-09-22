#!/usr/bin/env bash
# DEMO 4b -- the same PLL, with NO CO-SIMULATION ANYWHERE.
#
# Demo 4 models the analog half of a co-simulation that already runs. This
# one starts from the situation almost every design is actually in: the
# analog netlist exists, the RTL exists, a specification exists in English,
# and nothing has ever wired them together. There is no testbench spanning
# the two halves, no DPI bridge, and no shared libngspice -- so there is
# also no golden probe, which in demo 4 is the FIRST thing that runs.
#
# What this demo is for is the two questions that raises:
#
#   1. Characterization asks where in its range each block is used. With
#      no closed loop, nothing can measure that. Here it is DECLARED, from
#      the specification, and every message the run prints about a
#      declared band says "declared, not measured" in those words.
#
#   2. Per-block models are not a system. The loop is closed afterwards in
#      PURE SystemVerilog: the composed models, the customer's own RTL,
#      one simulator, no SPICE. The topology is stated; the SENSE of each
#      gate the digital side drives is derived from what the run measured.
#
#   DEMO_PAUSE=1 ./demo_4b_pll_nocosim.sh    pause between acts

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S2R="${S2R:-$HOME/spice2rnm}"
COSIM="${COSIM:-$HOME/ams-cosim}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
UVM_MS_LIB="${UVM_MS_LIB:-$HOME/uvm_ms_demo/ms}"
UVM_SRC="${UVM_SRC:-$HOME/iverilog-unified/uvm-core/src}"
XEZIM="${XEZIM:-$HOME/xezim/target/release/xezim}"
OUT="$HOME/s2r_runs/demo4b_pll"
# START FROM EMPTY, for the reason demos 1-4 do: a previous run's files
# linger otherwise, and the day the tool stops emitting one of them a
# stale copy gets published beside today's model. Guarded to this run
# directory, which is a variable a reader may edit.
REUSE=0
if [ "${DEMO_REUSE:-0}" = "1" ] && [ -f "$OUT/result.json" ]; then
  REUSE=1
else
  case "$OUT" in
    "$HOME"/s2r_runs/?*) rm -rf "$OUT" "$OUT.log" ;;
    *) echo "refusing to clean unexpected OUT: $OUT" >&2; exit 1 ;;
  esac
fi
mkdir -p "$OUT"

PLL_SRC="$COSIM/examples/pll"
PLL="$HOME/s2r_runs/demo4b_pll_deck"
NETLIST="$PLL/pll_analog.cir"
SPEC="$PLL/pll_spec.md"
LOOPSPEC="$PLL/pll_loop.json"

hr()  { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '=%.0s' {1..72})"; }
say() { printf '  %s\n' "$*"; }
beat(){ [ "${DEMO_PAUSE:-0}" = "1" ] && { printf '\n  [enter] '; read -r _; }; return 0; }

miss=0
need() {  # need <path> <what it is> <where it comes from>
  if [ -e "$1" ]; then
    printf '  \033[32mok\033[0m    %-34s %s\n' "$2" "$1"
  else
    printf '  \033[31mMISS\033[0m  %-34s %s\n' "$2" "$3"
    miss=1
  fi
}

hr "0. What this one needs, and what it does not"
say "Three inputs, and they are not connected to each other."
echo
need "$PLL_SRC/pll_analog.cir"  "the analog netlist"       "github.com/vrajeshprakhya/ams-cosim"
need "$PLL_SRC/pfd.sv"          "phase detector RTL"       "same repo, examples/pll"
need "$PLL_SRC/divn.sv"         "divider RTL"              "same repo, examples/pll"
need "$HERE/harness/pll_spec.md"   "the specification, in English" "this repo, harness/"
need "$HERE/harness/pll_loop.json" "how the loop is wired"         "this repo, harness/"
need "$NGSPICE"                 "ngspice binary"           "a normal ngspice build"
need "$XEZIM"                   "the SV simulator"         "xezim, release build"
need "$UVM_MS_LIB"             "the Accellera UVM-MS library" "for act 7 only; the rest runs without it"
if [ "$miss" = "1" ]; then
  echo; say "Nothing was run."
  exit 1
fi
echo
say "And what demo 4 needs that this one does NOT:"
say ""
say "  tb_pll.sv        a testbench spanning both halves   -- there is none"
say "  ams_bridge.so    the DPI bridge                     -- not built"
say "  libngspice.so    a SHARED ngspice for it to dlopen  -- not needed"
say ""
say "Those three are what a co-simulation is made of. This demo runs"
say "ngspice on the analog alone, and xezim on SystemVerilog alone, and"
say "the two never talk to each other."
beat

# The deck this demo runs: the published one with ONE line added, 20 mV
# rms on its supply. Same operating condition as demo 4, added here rather
# than published as a second netlist to keep in step. ASSERTED, not
# assumed -- a pattern that matched nothing would leave a quiet deck
# behind while every line below still described a noisy one.
[ "$REUSE" = "1" ] || rm -rf "$PLL"
mkdir -p "$PLL"
cp "$PLL_SRC/pfd.sv" "$PLL_SRC/divn.sv" "$PLL/"
cp "$HERE/harness/pll_spec.md"   "$SPEC"
cp "$HERE/harness/pll_loop.json" "$LOOPSPEC"
sed 's/^vdd dd 0 dc {vcc}$/vdd dd 0 dc {vcc} trnoise(0.02 1e-10 0 0)/' \
    "$PLL_SRC/pll_analog.cir" > "$NETLIST"
if ! grep -q 'trnoise' "$NETLIST"; then
  echo
  say "The supply card in $PLL_SRC/pll_analog.cir is not the shape this demo"
  say "expects, so the noise was not added and nothing was run. Looked for a"
  say "line reading exactly: vdd dd 0 dc {vcc}"
  exit 1
fi

cd "$S2R" || exit 1

hr "1. What breaks when the halves are not connected"
say "Demo 4's first act is a golden probe: the co-simulation runs against"
say "the TRANSISTORS before anything is characterised, and measures the"
say "voltage band each block actually works over. It has to be first,"
say "because that band is a property of the CLOSED loop -- it exists only"
say "once the digital side is attached."
echo
say "Here nothing is attached, so there is no probe and no band. Worse,"
say "two nets inside the ring are driven by nothing at all with the loop"
say "open, and have no operating point either:"
echo
grep -nE '^xinv1[12] ' "$NETLIST" | sed 's/^/    /'
echo
say "Run blind, those two buffers report their input ports FLOATING, and"
say "the oscillator gets characterised over its whole 0.5..2.8 V range"
say "rather than the 200 mV the loop uses."
beat

hr "2. What replaces the probe: the specification"
say "The band does not have to be measured. It has to be TRUE. The"
say "specification states it, in the table a designer writes anyway:"
echo
sed -n '/^| Control voltage/p;/^| Supply (VDD)/p' "$SPEC" | sed 's/^/    /'
echo
say "and the two ring nodes are full-swing CMOS between those rails,"
say "while the substrate and well ties do not move at all. Five bands,"
say "every one of them derivable from the spec above and the netlist --"
say "NONE of them copied from a probe that did not run:"
echo
say "  --band vout=1.75:1.95          the control window, from the table"
say "  --band xvco.outm1=0:3.3        rail to rail, inside the ring"
say "  --band xvco.outm2=0:3.3        the same"
say "  --band xvco.sub=0:0            substrate tie"
say "  --band xvco.well=3.3:3.3       well tie"
echo
say "A declared band is not a measured one, and the run never pretends"
say "otherwise: every message that uses one says so in those words. Act 4"
say "reads them back off the log."
beat

hr "3. One command"
say "  python3 -m spice2rnm \\"
say "      $NETLIST \\"
say "      --hierarchical --emit-assertions \\"
say "      --spec $SPEC \\"
say "      --band vout=1.75:1.95 \\"
say "      --band xvco.outm1=0:3.3 --band xvco.outm2=0:3.3 \\"
say "      --band xvco.sub=0:0 --band xvco.well=3.3:3.3 \\"
say "      --emit-uvm-ms --uvm-ms-lib $UVM_MS_LIB \\"
say "      --emit-rtl-loop $OUT/rtl_loop \\"
say "      --rtl-loop-spec $LOOPSPEC --run-rtl-loop \\"
say "      --out-dir $OUT"
echo
say "The RTL is not passed to characterization at all -- it has nothing to"
say "say about how a transistor behaves. It is read at the end, by"
say "--emit-rtl-loop, for its module headers."
echo
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  say "ANTHROPIC_API_KEY is NOT set here, so --spec will fail safe and the"
  say "run proceeds on the netlist and the bands alone. Everything below"
  say "reads the run's own output, so it will say what actually happened."
  echo
fi

if [ "$REUSE" = "1" ]; then
  printf '\n  \033[33m%s\033[0m\n' "DEMO_REUSE=1 -- NOT RUN. Everything below is read from the run"
  printf '  \033[33m%s\033[0m\n\n' "already in $OUT, which was made at $(date -r "$OUT/result.json" '+%Y-%m-%d %H:%M')."
  rc=0
  [ -f "$OUT.rc" ] && rc=$(cat "$OUT.rc")
  mins="?"
else
  t0=$(date +%s)
  python3 -m spice2rnm \
    "$NETLIST" \
    --hierarchical --emit-assertions \
    --spec "$SPEC" \
    --band vout=1.75:1.95 \
    --band xvco.outm1=0:3.3 --band xvco.outm2=0:3.3 \
    --band xvco.sub=0:0 --band xvco.well=3.3:3.3 \
    --emit-uvm-ms --uvm-ms-lib "$UVM_MS_LIB" \
    --emit-rtl-loop "$OUT/rtl_loop" \
    --rtl-loop-spec "$LOOPSPEC" --run-rtl-loop \
    --out-dir "$OUT" \
    --ngspice-bin "$NGSPICE" --xezim-bin "$XEZIM" \
    > "$OUT.log" 2>&1
  rc=$?
  echo "$rc" > "$OUT.rc"
  mins=$(( ($(date +%s) - t0) / 60 ))
  say "finished in ${mins} min, exit $rc."
fi

# A NONZERO EXIT IS NOT A RUN THAT DID NOTHING. The pipeline exits 1 when
# any block reports failure, and on this deck one does: a buffer inside
# the ring, which the open loop drives with nothing. That is a result to
# read, not a reason to print a tail and stop -- the acts below include
# the one where the loop closes. What would be a reason to stop is no
# result at all.
if [ ! -f "$OUT/result.json" ]; then
  echo; say "the run produced no result.json, so there is nothing to show."
  say "see $OUT.log"; tail -20 "$OUT.log"; exit 1
fi
if [ "$rc" != "0" ]; then
  echo
  say "The run exited $rc. It is reported here rather than hidden, and act 5"
  say "says which block it was and why the open loop cannot reach it."
fi
beat

hr "4. Where the numbers came from, in the run's own words"
say "A band that was declared is never reported as measured:"
echo
grep -aE "which a spec DECLARES as|which the golden co-simulation put in" "$OUT.log" \
  | sed "s/^.*\(block '\)/\\1/" | cut -c1-230 | fold -s -w 70 \
  | sed 's/^/    /' | head -12
echo
say "and the blocks the open loop cannot reach say that too, rather than"
say "quietly characterising something else:"
echo
grep -aE "cannot characterize in context" "$OUT.log" \
  | sed "s/^.*\(block '\)/\\1/" | cut -c1-230 | fold -s -w 70 \
  | sed 's/^/    /' | head -8
beat

hr "5. What came out"
say "Five models, by four different routes, none of them a transfer"
say "function fit for the three that matter:"
echo
find "$OUT" -maxdepth 2 -name '*_rnm.sv' | sort | sed "s|$OUT/|    |"
echo
say "and the run states its own limits rather than leaving them to be"
say "discovered -- including which block it could not reach, and which"
say "one it could not model:"
echo
python3 - "$OUT/result.json" <<'PY'
import json, math, sys


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


r = json.load(open(sys.argv[1]))["result"]
for row in (r.get("block_results") or []):
    pr = row.get("pipeline_result") or {}
    if pr.get("success") is not False:
        continue
    eq = pr.get("equivalence") or {}
    rms, thr = num(eq.get("rms_error_norm")), num(eq.get("threshold"))
    if rms is None or not math.isfinite(rms):
        how = ("emitted a NON-FINITE model: it diverged rather than missing "
               "a tolerance, so there is no score to report")
    elif thr is None:
        how = "scored rms %.4f, against no recorded threshold" % rms
    else:
        how = "missed its tolerance, rms %.4f against %.2f" % (rms, thr)
    print("    block %-6s %s" % (row["block"]["name"], how))
PY
echo
grep -aE "wrapper equivalence|structural wrapper|cosim system" "$OUT.log" \
  | sed 's/^[0-9TZ:.-]* *//' | cut -c1-150 | sed 's/^/    /' | head -5
beat

hr "6. The environments it generates, and the one it will not"
say "Three of the five blocks get a full UVM-MS environment -- agent,"
say "sequencer, scoreboard, the lot -- and nothing about that needed the"
say "co-simulation either:"
echo
grep -aE "^  [a-z0-9_]+ +[0-9]+ files in " "$OUT.log" | sed 's/^/  /'
echo
say "The other two are refused, with what writing one would take:"
echo
grep -aE "^  [a-z0-9_]+ +not generated -- " "$OUT.log" \
  | fold -s -w 70 | sed 's/^/    /'
echo
say "And there is NO system environment in this flow. In demo 4 its"
say "goldens are the per-window statistics of the TRANSISTOR run, reduced"
say "by the same functions the co-simulation's own verdict uses. Here"
say "there is no transistor run, so there is nothing for it to carry --"
say "and an environment scoring the models against the models would be"
say "the model marking its own work. What replaces it is the next act:"
say "the loop itself, required to reach a frequency it does not set."
beat

hr "7. And those environments, running"
say "Generating a file is not the same as the file working. Each of the"
say "three is elaborated, compiled against the Accellera library and run,"
say "and what its scoreboard concluded is printed here."
echo
if [ ! -d "$UVM_MS_LIB" ]; then
  say "NOT RUN: the Accellera UVM-MS library is not at $UVM_MS_LIB."
  say "The environments above were still generated; this act is the only"
  say "part of this demo that needs the library."
else
  n_env=0
  for scr in $(find "$OUT" -name 'run_*_ms.sh' | sort); do
    d="$(dirname "$scr")"
    blk="$(basename "$scr" .sh)"; blk="${blk#run_}"; blk="${blk%_ms}"
    t0=$(date +%s)
    ( cd "$d" && UVM_MS_LIB="$UVM_MS_LIB" UVM_SRC="$UVM_SRC" \
        timeout 1800 bash "$(basename "$scr")" > "$d/_ms_run.log" 2>&1 )
    rc=$?
    el=$(( $(date +%s) - t0 ))
    n_env=$(( n_env + 1 ))
    printf '    %-8s exit %d, %ds\n' "$blk" "$rc" "$el"
    grep -aE 'SB_SUMMARY|UVM_ERROR :|UVM_FATAL :|COMPILE FAILED' \
      "$d/_ms_run.log" | sed 's/.*\[SB_SUMMARY\] //; s/^UVM_INFO.*//' \
      | grep -avE '^[[:space:]]*[0-9]*$' | cut -c1-150 | sed 's/^/      /'
    echo
  done
  say "$n_env environment(s) run. Their scoreboards are generated too, so"
  say "a green one is only worth what the checks behind it measure --"
  say "which is why each line above says how many checks it ran and what"
  say "the worst of them was."
fi
beat

hr "8. Closing the loop, with no SPICE in it"
say "Per-block models are evidence about each block alone. The loop asks a"
say "different question, and answering it here needs no co-simulation at"
say "all: the composed models are pure SystemVerilog, and so is the RTL."
echo
say "What the spec file STATES is topology -- which RTL port lands on"
say "which net -- because connectivity is not recoverable from a model,"
say "and on this circuit a name is actively misleading."
echo
python3 - "$LOOPSPEC" <<'PY'
import json, sys, textwrap
d = json.load(open(sys.argv[1]))
for r in d["rtl"]:
    for port, sig in r["connect"].items():
        print("    %-6s . %-8s -> %s" % (r["module"], port, sig))
for sig, net in d["square"].items():
    print("    %-6s   %-8s -> %s" % ("analog", net, sig))
PY
echo
say "What it does NOT state is the sense of either pump gate. That is"
say "DERIVED, from two things characterization measured -- the sign of the"
say "tuning curve and the direction of the current each control state"
say "drives -- and the run prints the numbers it used:"
echo
grep -aE "^  (pdn|pupb) <-|^      (block|with cpump)" "$OUT.log" \
  | cut -c1-200 | sed 's/^/  /' | head -14
echo
say "pupb is active LOW and pdn is active HIGH on the same pump. That is"
say "not a distinction a port name survives, and a charge pump wired from"
say "its names has shipped upside down before."
beat

hr "9. And the loop, running"
say "One simulator. No bridge, no shared libngspice, no SPICE process."
echo
grep -aE "^  \[rtl-loop\]" "$OUT.log" | sed 's/^/  /'
echo
say "The control voltage is the number to read: it is where the loop"
say "stores its state, so a model that settles anywhere else disagrees"
say "there first."
beat

hr "Summary"
# READ FROM THE RUN, NOT TYPED, for the reason demos 1-4 are: a summary
# that cannot disagree with its own output is marking its own homework.
models=$(find "$OUT" -maxdepth 2 -name '*_rnm.sv' | wc -l)
verdict=$(grep -aoE '\[rtl-loop\] VERDICT [A-Z]+' "$OUT.log" | tail -1 | awk '{print $3}')
# Squeezed: these come out of a report that pads its own columns, and a
# label printed here as well as captured there reads as "vout vout".
squeeze() { tr -s ' '; }
rate=$(grep -aoE '\[rtl-loop\] rate .*' "$OUT.log" | tail -1 \
       | sed 's/.*rate *//' | squeeze | cut -c1-105)
vout=$(grep -aoE '\[rtl-loop\] net vout .*' "$OUT.log" | tail -1 \
       | sed 's/.*net *vout *//' | squeeze | cut -c1-105)
derived=$(grep -acE '^  (pdn|pupb) <- .*\(derived\)' "$OUT.log")
declared=$(grep -acE 'DECLARES as .*not measured' "$OUT.log")

blockfail=$(python3 - "$OUT/result.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["result"]
bad = [row["block"]["name"] for row in (r.get("block_results") or [])
       if (row.get("pipeline_result") or {}).get("success") is False]
print(" ".join(bad))
PY
)
say "co-simulation : none, at any stage"
say "pipeline exit : $rc${blockfail:+  (block(s) reporting failure: $blockfail)}"
say "models        : $models emitted"
say "bands         : $declared message(s) name a DECLARED band as declared"
envs=$(grep -acE "^  [a-z0-9_]+ +[0-9]+ files in " "$OUT.log")
noenv=$(grep -acE "^  [a-z0-9_]+ +not generated -- " "$OUT.log")
say "environments  : $envs generated, $noenv refused with a reason,"
say "                0 system -- it would need the transistor run"
ran=$(find "$OUT" -name "_ms_run.log" 2>/dev/null | wc -l)
sbfail=$(grep -ah "SB_SUMMARY" $(find "$OUT" -name "_ms_run.log" 2>/dev/null) 2>/dev/null | grep -aoE "failed=[1-9][0-9]*" | wc -l)
say "                $ran run, $sbfail scoreboard(s) reporting a failure"
say "loop wiring   : $derived gate sense(s) derived from measurement"
say "loop          : ${verdict:-?}"
[ -n "$rate" ] && say "                $rate"
[ -n "$vout" ] && say "                vout      $vout"
say ""
say "Scope, precisely: this holds lock from the initial condition the deck"
say "states, at one operating point, one corner, one reference rate. It is"
say "NOT evidence about the transistors -- none were simulated in the loop,"
say "and a loop that settles somewhere plausible and wrong still settles."
say "Demo 4 is the one that compares against transistors; it costs a"
say "co-simulation to do it."
say ""
say "run: $OUT/result.json   log: $OUT.log"
echo
