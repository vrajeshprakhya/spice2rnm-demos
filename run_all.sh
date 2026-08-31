#!/usr/bin/env bash
# Run all three demos and summarise. Useful before presenting, and as the
# check that a change to spice2rnm did not move anything the demos claim.
#
# Each demo's headline numbers are extracted with ITS OWN patterns rather
# than one shared filter. A shared one produced a report that silently
# dropped demo 3's scoreboard result: "measured 9 of 9 settings" appears
# twice in that output (once from the CLI, once echoed as a warning), and a
# head -N meant to keep the report short spent both of its remaining lines
# on the duplicate. The run was fine; the report was not, which is the worse
# of the two failures because it looks like the run.
#
#   ./run_all.sh            run all three
#   ./run_all.sh demo_2     run just the ones matching
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 1
FILTER="${1:-}"
LOGDIR="${TMPDIR:-/tmp}/spice2rnm_demos"
mkdir -p "$LOGDIR"

DEMOS=(demo_1_lpf.sh demo_2_dcc.sh demo_3_pi.sh)
total=0
ran=0
RAN_THIS_TIME=""   # only these get reported; see below

for d in "${DEMOS[@]}"; do
  [ -n "$FILTER" ] && [[ "$d" != *"$FILTER"* ]] && continue
  s=$(date +%s)
  bash "$d" > "$LOGDIR/${d%.sh}.out" 2>&1
  rc=$?
  el=$(( $(date +%s) - s ))
  total=$(( total + el ))
  ran=$(( ran + 1 ))
  RAN_THIS_TIME="$RAN_THIS_TIME $d"
  printf '  %-16s %4d s   exit %d\n' "$d" "$el" "$rc"
done
[ "$ran" -gt 1 ] && printf '  %-16s %4d s\n' TOTAL "$total"

# One field per line, deduplicated, so a value that happens to be printed
# twice cannot crowd out a different one.
field() {  # log, label, pattern
  local log="$1" label="$2" pat="$3" v
  [ -f "$log" ] || return
  v=$(grep -hoE "$pat" "$log" | head -1)
  [ -n "$v" ] && printf '    %-14s %s\n' "$label" "$v"
}

# Report only what ran THIS time. The logs persist between invocations, so
# reporting whatever is on disk meant `./run_all.sh demo_3` printed demo 1
# and demo 2's numbers from an earlier run, formatted identically to fresh
# ones. Stale results presented as current are worse than no results.
ran_this() { [[ " $RAN_THIS_TIME " == *" $1 "* ]]; }

L="$LOGDIR/demo_1_lpf.out"
if ran_this demo_1_lpf.sh && [ -f "$L" ]; then
  echo
  echo '  demo 1  LPF'
  field "$L" chirp   'rms_error_norm=[0-9.]+'
  field "$L" PRBS    'rms 0\.[0-9]+ normalized'
  field "$L" 'DC'    'dc checks=[0-9]+ failed=[0-9]+'
  field "$L" 'AC'    'ac checks=[0-9]+ failed=[0-9]+'
fi

L="$LOGDIR/demo_2_dcc.out"
if ran_this demo_2_dcc.sh && [ -f "$L" ]; then
  echo
  echo '  demo 2  DCC'
  field "$L" transient 'rms_error_norm=[0-9.]+'
  field "$L" 'duty null' '50% duty null at vctrl = [0-9.]+ V'
  field "$L" 'DC'      'dc checks=[0-9]+ failed=[0-9]+'
  field "$L" 'AC'      'ac checks=0 \(no AC golden'
fi

L="$LOGDIR/demo_3_pi.out"
if ran_this demo_3_pi.sh && [ -f "$L" ]; then
  echo
  echo '  demo 3  PI'
  field "$L" settings  'measured [0-9]+ of [0-9]+ settings'
  field "$L" traversal 'traversal [-0-9.]+ ps, LSB [-0-9.]+ ps, [a-z]+'
  field "$L" phase     'phase checks=[0-9]+ failed=[0-9]+ \| worst [0-9.]+ ps'
  field "$L" DNL       'DNL worst *: [-+0-9.]+ ps *\([-+0-9.]+ LSB\)'
fi

echo
echo '  problems'
scan=""
for d in $RAN_THIS_TIME; do scan="$scan $LOGDIR/${d%.sh}.out"; done
found=$(grep -inE 'command not found|Traceback|COMPILE FAILED|UVM_FATAL : *[1-9]|No such file' \
  $scan 2>/dev/null | head -5)
if [ -n "$found" ]; then
  echo "$found" | sed 's/^/    /'
else
  echo '    none'
fi
echo
echo "  logs: $LOGDIR"
