#!/usr/bin/env bash
# Run all four demos and summarise. Useful before presenting, and as the
# check that a change to spice2rnm did not move anything the demos claim.
#
# Demo 4 is not self-contained: it models the analog half of a
# co-simulation, so it needs the other half -- the RTL, the DPI bridge, and
# a SHARED libngspice, which is a different ngspice build from the binary
# the others use. It checks for those and exits 1 naming what is missing, so
# a machine without them reports a skip here rather than a failure.
#
# Each demo's headline numbers are extracted with ITS OWN patterns rather
# than one shared filter, and one field per line, deduplicated -- so a
# value that happens to be printed twice in a demo's output can never
# crowd a different value out of the report.
#
#   ./run_all.sh            run all four
#   ./run_all.sh demo_2     run just the ones matching
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 1
FILTER="${1:-}"
LOGDIR="${TMPDIR:-/tmp}/spice2rnm_demos"
mkdir -p "$LOGDIR"

DEMOS=(demo_1_lpf.sh demo_2_dcc.sh demo_3_pi.sh demo_4_pll.sh)
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
  # A demo that exited because its prerequisites are absent has not failed,
  # and reporting it as a failure would make the summary useless on any
  # machine without the co-simulation. It says so itself; repeat that.
  if grep -q 'Nothing was run' "$LOGDIR/${d%.sh}.out" 2>/dev/null; then
    printf '  %-16s %4d s   SKIPPED -- prerequisites absent\n' "$d" "$el"
    RAN_THIS_TIME="${RAN_THIS_TIME% $d}"
  else
    printf '  %-16s %4d s   exit %d\n' "$d" "$el" "$rc"
  fi
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

# Report only what ran THIS time. The logs persist between invocations,
# and a stale result presented as current is worse than no result.
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
  # The section that REPLACES AC for this model. Reported explicitly: a
  # demo whose only frequency-domain line reads "checks=0" looks like
  # something was skipped rather than like something was substituted.
  field "$L" 'duty'    'duty checks=[0-9]+ failed=[0-9]+ \| worst [0-9.]+ pp'
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

L="$LOGDIR/demo_4_pll.out"
if ran_this demo_4_pll.sh && [ -f "$L" ]; then
  echo
  echo '  demo 4  PLL'
  field "$L" equivalence 'equivalence  : [0-9]+ pass, [0-9]+ fail'
  field "$L" floor       'floor        : [A-Z]+'
  field "$L" system      'system       : [A-Z]+ -- [0-9]+ boundary signal\(s\), [0-9]+ failed'
  field "$L" vout        'vout worst \|diff\| [0-9.e-]+ V'
  field "$L" lock        'locked within [-0-9.]+% of [0-9.]+ MHz'
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
