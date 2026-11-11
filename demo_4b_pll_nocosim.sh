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
#      no closed loop, nothing can measure that. So it is read off the two
#      artifacts that do know: the DECK, for what the deck decides (a
#      substrate tie is a source card; a logic swing is a pair of rails),
#      and the SPECIFICATION, for the one number only a document holds --
#      where a locked loop keeps its control voltage. Derived and declared
#      are not measured, and every message the run prints about a band
#      says which of the three it is, in those words.
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

PLL_SRC="${PLL_SRC:-$HERE/rtl/pll}"
PLL="$HOME/s2r_runs/demo4b_pll_deck"
NETLIST="$PLL/pll_analog.cir"
SPEC="$PLL/pll_spec.md"

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
need "$HERE/netlists/pll_analog.cir" "the analog netlist"  "this repo, netlists/"
need "$PLL_SRC/pfd.sv"          "phase detector RTL"       "this repo, rtl/pll/"
need "$PLL_SRC/divn.sv"         "divider RTL"              "this repo, rtl/pll/"
need "$HERE/specs/pll_spec.md"     "the specification, in English" "this repo, specs/"
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
say "  tb_pll.sv        a testbench spanning both halves   -- not read here"
say "  ams_bridge.so    the DPI bridge                     -- not built"
say "  libngspice.so    a SHARED ngspice for it to dlopen  -- not needed"
say ""
say "Those three are what a co-simulation is made of. This demo runs"
say "ngspice on the analog alone, and xezim on SystemVerilog alone, and"
say "the two never talk to each other."
beat

# The deck this demo runs is published in netlists/: the ams-cosim
# example with ONE line added, 20 mV rms on its supply, the operating
# condition the specification states. Demo 4 and demo 4b run the same
# file. ASSERTED, not assumed -- a deck without that card would leave a
# quiet circuit behind while every line below still described a noisy
# one.
[ "$REUSE" = "1" ] || rm -rf "$PLL"
mkdir -p "$PLL"
cp "$PLL_SRC/pfd.sv" "$PLL_SRC/divn.sv" "$PLL/"
cp "$HERE/specs/pll_spec.md"     "$SPEC"
cp "$HERE/netlists/pll_analog.cir" "$NETLIST"
if ! grep -q '^vdd dd 0 dc {vcc} trnoise(0.02 1e-10 0 0)$' "$NETLIST"; then
  echo
  say "netlists/pll_analog.cir does not carry the supply-noise card this demo"
  say "runs under, so nothing was run. Expected a line reading exactly:"
  say "  vdd dd 0 dc {vcc} trnoise(0.02 1e-10 0 0)"
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

hr "2. What replaces the probe: the deck, and the specification"
say "The band does not have to be measured. It has to be TRUE. And four"
say "of the five are not opinions at all -- they are in the deck, which"
say "is read rather than restated:"
echo
grep -nE '^(ve|vpe) ' "$NETLIST" | sed 's/^/    /'
echo
say "A source holding a node at one voltage IS that node's band, and the"
say "two ring nodes sit between a pull-down to 0 V and a pull-up to the"
say "rail, so they cannot leave them. Nothing about either needs saying"
say "twice."
echo
say "The ONE number that is not in the netlist is where a LOCKED loop"
say "keeps its control voltage, and that is in the specification, in the"
say "table a designer writes anyway:"
echo
sed -n '/^| Control voltage/p;/^| Supply (VDD)/p' "$SPEC" | sed 's/^/    /'
echo
say "which is read by TEXT, not by a model: a band decides the range a"
say "block is MEASURED over, so unlike every other field a spec supplies"
say "it cannot be checked against a measurement afterwards -- it chose"
say "the measurement. A number with that much authority must not move"
say "depending on whether a model happened to be reachable."
echo
say "And nothing names a net anywhere. The spec says 'control voltage',"
say "the deck says 'cont', and the x card says cont is the top level's"
say "vout; what binds the three is the measurement that found which port"
say "tunes the oscillator. Act 4 reads that back off the log."
echo
say "A declared band is still not a measured one, and the run never"
say "pretends otherwise: measured, derived and declared are three"
say "different words and every message that uses a band says which."
beat

hr "3. One command"
say "  python3 -m spice2rnm \\"
say "      $NETLIST \\"
say "      $PLL/pfd.sv $PLL/divn.sv \\"
say "      --hierarchical --emit-assertions \\"
say "      --spec $SPEC \\"
say "      --emit-uvm-ms --uvm-ms-lib $UVM_MS_LIB \\"
say "      --out-dir $OUT"
echo
say "THE OPERATING BANDS ARE NOT ON THIS LINE. They were, for a while:"
say "five --band flags, the one above in the middle of them. A number"
say "typed on a command line has no source -- it cannot be traced to"
say "the document that justifies it, it is not reviewed with the design,"
say "and five of them in a shell script drift from the specification"
say "they were copied out of without anything noticing. The deck and the"
say "spec are artifacts somebody owns; this line is not."
echo
say "The .sv files are sorted from the netlist by suffix, not by"
say "position. They reach characterization nowhere: RTL has nothing to"
say "say about how a transistor behaves. They are read once, at the end,"
say "for their module headers -- which is where the loop's wiring comes"
say "from now, instead of from a file this repo used to ship."
echo
say "AND THERE IS NO FLAG ASKING FOR THE LOOP. Passing the RTL with no"
say "co-simulation testbench among it is what asks for it, so that is"
say "what the tool acts on; it lands in rtl_loop/ under --out-dir like"
say "every other artifact, and it is run rather than merely written."
say "--no-rtl-loop is the way to say no."
echo
# WHETHER A MODEL CAN BE REACHED, asked of the tree being run rather than
# assumed from the name of an environment variable. This script tested
# ANTHROPIC_API_KEY long after the pipeline moved to Claude on Amazon
# Bedrock, so it was reporting the absence of something nothing reads --
# and on a machine with working Bedrock credentials it would have said
# the model part was off while that part ran.
#
# THE TREE NOW HAS TWO BACKENDS, so the probe asks which one this run
# would take before deciding what would stop it: demanding botocore on a
# run that reaches Claude's own API with a key would report the model off
# while that part ran, which is the same mistake in the other direction.
llm_state=$(cd "$S2R" && python3 - <<'PY' 2>/dev/null
import importlib.util as iu


def sdk_missing(which):
    """Why no call could be made from here, SDK-wise, on this backend.

    unavailable() answers about CONFIGURATION only and says so: it
    checks the credentials and leaves their validity to surface on the
    first request. But SECURITY.md's first condition for a call is that
    the optional client is INSTALLED, and nothing checks that -- so a
    credential set with no SDK present answers "reachable" and every
    advisor call then dies on an import. This narration must not claim
    the advisor was consulted when it could not be.
    """
    if iu.find_spec("anthropic") is None:
        return "the Claude client is not installed (pip install spice2rnm[llm])"
    import anthropic
    if which == "bedrock":
        if not hasattr(anthropic, "AnthropicBedrock"):
            return "the installed anthropic client has no Bedrock support"
        if iu.find_spec("botocore") is None:
            return "botocore is absent, so a Bedrock request cannot be signed"
    elif not hasattr(anthropic, "Anthropic"):
        return "the installed anthropic client has no first-party client"
    return None


try:
    from spice2rnm import llm_client
    which = llm_client.backend()
    why = llm_client.unavailable() or sdk_missing(which)
except Exception:                      # a tree that reads a key directly
    import os
    which = "api"
    why = (None if os.environ.get("ANTHROPIC_API_KEY")
           else "no ANTHROPIC_API_KEY in the environment")
print("REACHABLE: %s" % which if not why else "UNAVAILABLE: %s" % why)
PY
)
case "$llm_state" in
  UNAVAILABLE:*)
    say "NO MODEL IS REACHABLE HERE: ${llm_state#UNAVAILABLE: }. So the"
    say "part of --spec a MODEL reads will fail safe. THE BANDS ARE NOT"
    say "AFFECTED: the operating-conditions table is parsed by text, for"
    say "exactly this reason -- a band decides what gets measured, so it"
    say "must not move depending on whether a model could be called."
    say "Everything below reads the run's own output, so it will say what"
    say "actually happened."
    echo
    ;;
  REACHABLE:*)
    say "A MODEL IS REACHABLE HERE (${llm_state#REACHABLE: }: either"
    say "Claude's own API with a key, or Amazon Bedrock in this machine's"
    say "own AWS account -- SECURITY.md states what that choice means for"
    say "the netlist), so the part of --spec a model reads will run. THE"
    say "BANDS STILL DO NOT DEPEND ON IT: the operating-conditions table"
    say "is parsed by text either way, because a band decides what gets"
    say "measured and must not move with whether a model could be called."
    echo
    ;;
  *)
    say "WHETHER a model is reachable from $S2R could not be determined"
    say "here. THE BANDS DO NOT DEPEND ON IT either way: the"
    say "operating-conditions table is parsed by text, and everything"
    say "below reads the run's own output."
    echo
    ;;
esac

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
    "$PLL/pfd.sv" "$PLL/divn.sv" \
    --hierarchical --emit-assertions \
    --spec "$SPEC" \
    --emit-uvm-ms --uvm-ms-lib "$UVM_MS_LIB" \
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
say "Three sources, three different words, and a band that was declared"
say "is never reported as measured:"
echo
grep -aE "which a spec DECLARES as|which the deck itself gives as|which the golden co-simulation put in" "$OUT.log" \
  | sed "s/^.*\(block '\)/\\1/" | cut -c1-230 | fold -s -w 70 \
  | sed 's/^/    /' | head -12
echo
say "and the bands themselves, each with the card or the table row it"
say "came from:"
echo
grep -aE "band for '[^']+' (DERIVED|DECLARED)" "$OUT.log" \
  | sed 's/^.*band for/band for/' | cut -c1-200 | fold -s -w 70 \
  | sed 's/^/    /' | head -14
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
say "Generating a file is not the same as the file working. Each one is"
say "elaborated, compiled against the Accellera library and run, and what"
say "its scoreboard concluded is printed here."
echo
if [ ! -d "$UVM_MS_LIB" ]; then
  say "NOT RUN: the Accellera UVM-MS library is not at $UVM_MS_LIB."
  say "The environments above were still generated; this act is the only"
  say "part of this demo that needs the library."
else
  # What the RUN said it emitted, so this act can tell whether it found
  # all of them. It could not before: the loop environment's script was
  # named out of the run_*_ms.sh family and was skipped in silence.
  n_said=$(( $(grep -acE "^  [a-z0-9_]+ +[0-9]+ files in " "$OUT.log") \
           + $(grep -acE "^  uvm-ms \(loop\): [0-9]+ files in " "$OUT.log") ))
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
  if [ "$n_env" -lt "$n_said" ]; then
    say "MISMATCH: the run emitted $n_said environment(s) and this act found"
    say "$n_env. The difference is an environment nothing here executed, so"
    say "its files are evidence that a generator ran and nothing more."
    echo
  elif [ "$n_env" -gt "$n_said" ] && [ "$REUSE" = "1" ]; then
    say "Found $n_env environment(s) where the log mentions $n_said. That is"
    say "DEMO_REUSE: the log belongs to whatever run is on disk, and this"
    say "one predates a generator whose output is still here."
    echo
  fi
  say "$n_env environment(s) run, of $n_said the run reports emitting."
  say "Their scoreboards are generated too, so"
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
say "NOTHING TELLS IT THE TOPOLOGY. This demo used to carry a JSON file"
say "naming which RTL port landed on which net. It does not any more: the"
say "wiring is followed out from the one clock the analog produces, by"
say "port DIRECTION, and not one port NAME is read on the way."
echo
say "That last part is the point. In ngspice's own PLL example the"
say "detector is wired \`Xfpdet d_divout d_ref\` against a subcircuit"
say "declared \`.subckt f-p-det d_R d_V\` -- so d_R carries the DIVIDED"
say "clock, the opposite of what it reads like. A wiring taken from names"
say "is confidently backwards there."
echo
say "Here is what it worked out, and what from:"
echo
python3 - "$OUT/rtl_loop/rtl_loop_derivation.json" <<'PY'
import json, sys, textwrap
try:
    d = json.load(open(sys.argv[1]))
except OSError:
    print("    (no derivation record -- the loop was not written)")
    raise SystemExit(0)
for r in d["rtl"]:
    for port, sig in r["connect"].items():
        print("    %-6s . %-8s -> %s" % (r["module"], port, sig))
for sig, net in d["square"].items():
    print("    %-6s   %-8s -> %s" % ("analog", net, sig))
print()
for f in d.get("_derived", []):
    # The wiring's own value is the port list printed above, so
    # only its provenance is worth repeating here.
    if f["what"] == "the wiring":
        print("    the wiring, as listed above")
    else:
        print(textwrap.fill("%s = %s" % (f["what"], f["value"]),
                            74, initial_indent="    ",
                            subsequent_indent="      "))
    print(textwrap.fill(f["from"], 70, initial_indent="        ",
                        subsequent_indent="        "))
PY
echo
say "The sense of each pump gate is derived too, and from measurements"
say "rather than from structure -- the sign of the tuning curve and the"
say "direction of the current each control state drives. The run prints"
say "the numbers it used:"
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
say "ONE THING ABOUT THIS LOOP IS NOT DERIVABLE FROM THE ANALOG AT"
say "ALL: which of the detector's outputs speeds the oscillator up is a"
say "fact about its body, and both wirings elaborate and run. It used to"
say "be settled by building both and seeing which locked. The"
say "specification states it instead -- one line, about the CONTROL"
say "VOLTAGE and not about any gate of the pump:"
echo
say "    The detector's \`up\` output raises the control voltage."
echo
say "AND THAT IS NOT THE SAME AS SPEEDING IT UP. This ring's tuning"
say "slope is negative, so raising the control voltage LOWERS the"
say "frequency; the run converts the one into the other using the slope"
say "it measured, and a loop wired as though they were the same is"
say "wired backwards. The act above printed that conversion."
echo
say "The other pairing is still built and run if this one does not"
say "lock, because a loop that locks is a measurement and a document is"
say "not. If they disagree the measurement wins and the run says the"
say "document is wrong about its own detector."
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
pairings=$(grep -acE '^  \[rtl-loop\] VERDICT ' "$OUT.log")
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
say "loop wiring   : $derived gate sense(s) derived from measurement,"
say "                0 stated by hand"
say "gate pairing  : $pairings harness(es) run; the loop settles which"
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
