#!/usr/bin/env bash
# Run every published UVM-MS environment and SAVE ITS OUTPUT, so the
# figures the docs quote can be checked without a toolchain.
#
# The showcase publishes each environment's sources but published no run
# of them, so docs/jitter.md's boundary jitter figure could not be
# checked against anything in this repository. This writes
# showcase/uvm_ms_runs/<case>/<env>.log, one per environment, plus a
# SUMMARY.txt per case that is the thing worth reading first.
#
# WHY THE LOGS DO NOT LIVE INSIDE THE CASE DIRECTORIES, which is where a
# reader would look for them first. refresh.sh begins each case with
# `rm -rf "$dst"` and rebuilds it from the run directory, so anything
# else left in showcase/pll_cosim/ disappears at the next refresh --
# README.md says as much, and that is why the case write-ups live under
# docs/ rather than beside the files they describe. These logs are not
# produced by a demo run at all: they come from running the PUBLISHED
# environment, which is the point of them, so they sit beside the cases
# rather than inside one.
#
# Usage:  ./run_uvm_ms.sh [--only CASE]... [--summary-only]
#
#   --summary-only   Rebuild each SUMMARY.txt from the logs already in
#                    uvm_ms_runs/, simulating nothing. Every figure a
#                    summary quotes is read out of a log, so the summary
#                    is derived rather than remembered, and a reader can
#                    regenerate it in a second to check that.
#
# What it needs, and why each default is what it is:
#
#   UVM_SRC     The block-level run scripts are generated with NO default
#               for this -- only the system environment's script defaults
#               it -- so running a block script with the variable unset
#               fails on "/uvm_pkg.sv not found", naming a path that
#               begins with a slash because the variable was empty.
#               Defaulted here so all eight run the same way.
#   UVM_MS_LIB  The MS library. The generated scripts already default it.
#   RTL_DIR     Only the system environment needs it: pfd.sv and divn.sv
#               are the design's OWN RTL, not generated, so they are not
#               published beside the environment and nothing in this
#               repository can supply them.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export UVM_SRC=${UVM_SRC:-$HOME/iverilog-unified/uvm-core/src}
export UVM_MS_LIB=${UVM_MS_LIB:-$HOME/uvm_ms_demo/ms}
export XEZIM=${XEZIM:-$HOME/xezim/target/release/xezim}
export RTL_DIR=${RTL_DIR:-$HOME/s2r_runs/demo4_pll_deck}

ONLY=""; SUMMARY_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="$ONLY $2"; shift 2 ;;
    --summary-only) SUMMARY_ONLY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ "$SUMMARY_ONLY" = "0" ]; then
  # Name every missing piece rather than the first, so one run tells a
  # reader everything they have to install.
  miss=0
  [ -x "$XEZIM" ]                    || { echo "MISSING: xezim at '$XEZIM' (set XEZIM)"; miss=1; }
  [ -f "$UVM_SRC/uvm_pkg.sv" ]       || { echo "MISSING: UVM at '$UVM_SRC' (set UVM_SRC)"; miss=1; }
  [ -f "$UVM_MS_LIB/uvm_ms_pkg.sv" ] || { echo "MISSING: UVM-MS at '$UVM_MS_LIB' (set UVM_MS_LIB)"; miss=1; }
  [ -f "$RTL_DIR/pfd.sv" ]           || echo "NOTE: no pfd.sv in '$RTL_DIR' -- the SYSTEM environment will be skipped (set RTL_DIR)"
  [ "$miss" = "0" ] || exit 1
fi

want() { [ -z "$ONLY" ] && return 0; case " $ONLY " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

# The simulator's revision. There is no --version: the flag is -V, and
# asking for the wrong one puts "Warning: unknown flag" where a revision
# belongs, which is what the first version of this script published. The
# git revision beside the binary is recorded too, because that is what
# STAMP names and the two should agree.
xezim_id() {
  local v rev repo
  v=$("$XEZIM" -V 2>&1 | head -1)
  repo=${XEZIM%/target/release/xezim}
  rev=$(git -C "$repo" rev-parse --short HEAD 2>/dev/null)
  [ -n "$rev" ] && echo "$v (git $rev)" || echo "$v"
}

# Counting errors has two traps, and they pull in opposite directions.
#
# A real event line looks like
#     UVM_ERROR path/file.svh(123) @ 42: uvm_test_top...
# while the end-of-run report summary tallies itself with
#     UVM_ERROR :    0
# so counting every line that merely STARTS with UVM_ERROR finds the
# summary's own tally and reports one error on a clean run.
#
# And the system environment prints NO report summary: its testbench
# calls $finish, which pre-empts UVM's report_phase, so reading the
# tally alone finds nothing, and an empty string is not zero. The events
# are counted, and the tally is used only as a cross-check where the run
# got far enough to print one.
uvm_events() { grep -ac -E "^$1 [^:]" "$2"; }
uvm_tally()  { grep -a -m1 -E "^$1 *:" "$2" | awk '{print $NF}'; }

# The elapsed time is read from the log rather than from this script's
# own clock, so --summary-only reproduces it and a reader can find the
# line it came from. It is the simulator's own total.
sim_ms() { grep -a -o '\[PHASE\] total: [0-9.]*ms' "$1" | tail -1 | awk '{print $3}'; }

total_fail=0
ran=0

# One environment's line in a SUMMARY, derived entirely from its log.
summarize_env() {   # log, blk, sum  ->  appends; returns 1 on a problem
  local log=$1 blk=$2 sum=$3 fin err fat note tally ms bad=0
  if grep -qa 'finish called' "$log"; then fin="finished"
  else fin="TRUNCATED"; bad=1; fi
  err=$(uvm_events UVM_ERROR "$log"); fat=$(uvm_events UVM_FATAL "$log")
  [ "$err" = "0" ] || bad=1
  [ "$fat" = "0" ] || bad=1
  note=""; tally=$(uvm_tally UVM_ERROR "$log")
  if [ -z "$tally" ]; then
    note="  (no UVM report summary: \$finish pre-empts report_phase)"
  elif [ "$tally" != "$err" ]; then
    note="  (the report summary says UVM_ERROR=$tally)"; bad=1
  fi
  ms=$(sim_ms "$log"); [ -n "$ms" ] || ms="?"
  printf '  %-10s %-9s %12s  UVM_ERROR=%s UVM_FATAL=%s%s\n' \
    "$blk" "$fin" "$ms" "$err" "$fat" "$note" | tee -a "$sum"
  # Each environment's own verdict, in its own words.
  grep -a -E '\[SB_SUMMARY\]|^aout:' "$log" \
    | sed -E 's/^.*\[SB_SUMMARY\]/    [SB_SUMMARY]/; s/^aout:/    aout:/' >> "$sum"
  echo >> "$sum"
  return $bad
}

OUT="$HERE/uvm_ms_runs"
for case_dir in "$HERE"/*/; do
  c=$(basename "$case_dir")
  [ -d "$case_dir/env" ] || continue
  want "$c" || continue
  out="$OUT/$c"

  if [ "$SUMMARY_ONLY" = "1" ]; then
    [ -d "$out" ] || { echo "== $c: no logs in $out -- run without --summary-only first"; continue; }
  else
    rm -rf "$out"; mkdir -p "$out"
  fi

  sum="$out/SUMMARY.txt"
  {
    echo "UVM-MS environments of $c, run from the sources published in ../../$c/env/."
    if [ "$SUMMARY_ONLY" = "1" ]; then
      echo "Summary rebuilt from the logs beside it by showcase/run_uvm_ms.sh --summary-only"
      echo "at $(date -u +%Y-%m-%dT%H:%M:%SZ); every figure below is read out of one of them."
    else
      echo "Written by showcase/run_uvm_ms.sh at $(date -u +%Y-%m-%dT%H:%M:%SZ)."
    fi
    echo "xezim: $(xezim_id)"
    echo "UVM:   $UVM_SRC"
    echo
    echo "The time is the simulator's own [PHASE] total from each log, not wall clock."
    echo
  } > "$sum"
  echo "== $c"

  for envdir in "$case_dir"env/*/uvm_ms/; do
    [ -d "$envdir" ] || continue
    blk=$(basename "$(dirname "$envdir")")
    script=$(cd "$envdir" && ls run_*.sh 2>/dev/null | head -1)
    [ -n "$script" ] || continue
    log="$out/$blk.log"

    if [ "$SUMMARY_ONLY" = "1" ]; then
      [ -f "$log" ] || { printf '  %-10s no log\n' "$blk" | tee -a "$sum"; continue; }
    else
      # The system environment cannot run without the design's own RTL.
      if [ ! -f "$RTL_DIR/pfd.sv" ] && [ "$blk" = "cosim" ]; then
        printf '  %-10s SKIPPED (no RTL_DIR holding pfd.sv and divn.sv)\n' "$blk" | tee -a "$sum"
        continue
      fi
      ( cd "$envdir" && bash "$script" ) > "$log" 2>&1
    fi

    ran=$((ran + 1))
    summarize_env "$log" "$blk" "$sum" || total_fail=$((total_fail + 1))
  done
done

echo
[ "$ran" -gt 0 ] || { echo "nothing to do -- check --only"; exit 1; }
if [ "$total_fail" = "0" ]; then
  echo "$ran environment(s) accounted for, no UVM errors"
else
  echo "$total_fail problem(s) across $ran environment(s) -- see the SUMMARY.txt files"; exit 1
fi
