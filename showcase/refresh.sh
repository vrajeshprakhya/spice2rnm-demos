#!/usr/bin/env bash
# Regenerate the showcase from the demos, so it can never go stale.
#
# Stale showcase artifacts would be exactly the model-drift problem the
# product exists to solve, so this is the only supported way to update
# this directory: run the demos, copy the deliverables, stamp the run.
# Hand-editing anything here other than README.md defeats the point.
#
#   ./refresh.sh              run all three demos, then curate
#   ./refresh.sh --no-run     curate from the existing run directories
#                             (only for iterating on the curation itself)
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMOS="$(cd "$HERE/.." && pwd)"
RUNS="$HOME/s2r_runs"

if [ "${1:-}" != "--no-run" ]; then
  ( cd "$DEMOS" && ./run_all.sh ) | tee /tmp/showcase_run_summary.txt
else
  echo "curating from existing run directories (--no-run)"
  : > /tmp/showcase_run_summary.txt
fi

# Deliverables and evidence only. The run directories also hold
# characterisation scratch, compiled simulator objects and DPI shims;
# a customer evaluating output quality wants the files they would keep,
# not the build products.
curate() {  # src-dir, dest-name
  local src="$RUNS/$1" dst="$HERE/$2"
  [ -d "$src" ] || { echo "MISSING run dir: $src (run the demos first)"; exit 1; }
  rm -rf "$dst"
  mkdir -p "$dst"
  local n=0 f
  for f in "$src"/*.sv "$src"/*.svh "$src"/run_*.sh \
           "$src"/result.json "$src"/pipeline.txt; do
    [ -f "$f" ] || continue
    cp "$f" "$dst/"
    n=$((n + 1))
  done
  # A curation that copied nothing is a broken refresh, not an empty case.
  [ "$n" -ge 3 ] || { echo "curation for $2 found only $n file(s)"; exit 1; }
  echo "  $2: $n files"
}

# The house-style case is not one of the demos: it is the same circuit as
# lpf2, generated a second time against the sample library in house_lib/,
# so the two directories can be diffed. Generated here rather than in a
# demo because it demonstrates an ADOPTION path, not a modelling one --
# and because its whole point is to sit next to lpf2 for comparison.
S2R="${S2R:-$HOME/spice2rnm}"
NGSPICE="${NGSPICE:-$HOME/ngspice-install/bin/ngspice}"
#
# Generated DIRECTLY into its published location, unlike the demo cases,
# and for a reason: the conformed run script references the house package
# by a path relative to itself, so that the artifact and the library it
# joined can be published, moved or copied together. Generating in a
# scratch directory and copying here afterwards would bake in a path
# correct for a directory this case does not live in.
if [ "${1:-}" != "--no-run" ]; then
  # --sim went away with the second simulator: spice2rnm 01ea4a9 ("one
  # simulator: xezim, and no Icarus anywhere") removed the flag, and this
  # kept passing it. argparse rejects an unknown flag outright, so the full
  # refresh has been failing here since -- while ./refresh.sh --no-run, which
  # skips this block, kept working. A path exercised only by the shorter
  # invocation is a path nobody runs until it matters.
  echo "generating the house-style case:"
  rm -rf "$HERE/lpf2_house"
  ( cd "$S2R" && python3 -m spice2rnm work/rc_lpf2.cir \
      --out-dir "$HERE/lpf2_house" \
      --input-node vin --output-node vout \
      --ngspice-bin "$NGSPICE" \
      --emit-uvm-ms --emit-assertions --style-from "$HERE/house_lib" \
      --model-ports house ) \
    | grep -E "house style|SUCCESS|FAILED" | sed 's/^/  /'
  # Same whitelist curate() applies, but in place: characterisation
  # scratch, waveform dumps and build products are not deliverables.
  find "$HERE/lpf2_house" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
  find "$HERE/lpf2_house" -mindepth 1 -maxdepth 1 -type f \
    ! -name '*.sv' ! -name '*.svh' ! -name 'run_*.sh' \
    ! -name 'result.json' ! -name 'pipeline.txt' -delete
  n=$(ls "$HERE/lpf2_house" | wc -l)
  [ "$n" -ge 3 ] || { echo "house-style case produced only $n file(s)"; exit 1; }
  echo "  lpf2_house: $n files"
fi

# The PLL curates differently, for two reasons.
#
# ITS DELIVERABLES ARE NOT AT THE RUN ROOT. The other three are single
# blocks and write their model beside their result.json; a hierarchical run
# writes one model per block in that block's own directory, plus the
# composed analog top under loop/analog. curate()'s root glob finds none of
# them and would trip its own "found only 0 files" guard.
#
# AND IT IS OPTIONAL. It needs the co-simulation it models -- RTL, the DPI
# bridge, a shared libngspice -- which the other three do not. curate()
# exits 1 on a missing run directory, which would mean nobody without that
# co-simulation could refresh this showcase at all. So a missing PLL run is
# reported and skipped.
curate_pll() {  # src-dir, dest-name
  local src="$RUNS/$1" dst="$HERE/$2"
  if [ ! -d "$src" ]; then
    echo "  $2: SKIPPED -- no run at $src (demo 4 needs the co-simulation)"
    return 0
  fi
  rm -rf "$dst"
  mkdir -p "$dst"
  local n=0 f
  # One model per block, from wherever the block wrote it.
  for f in "$src"/*/*_rnm.sv; do
    [ -f "$f" ] || continue
    cp "$f" "$dst/"; n=$((n + 1))
  done
  # The composed analog top and the interfaces it instantiates: the thing
  # the RTL actually binds to, which no single block file is.
  #
  # cosim/, not loop/. This function was written an hour before spice2rnm
  # renamed that directory, and then silently curated six files instead of
  # eleven -- the guard below only fires under three, so a case missing its
  # composed top passed. Both spellings are accepted because a run made
  # before the rename still has loop/, and a showcase that cannot curate
  # last week's run is a worse answer than one that reads both.
  for f in "$src"/cosim/analog/*.sv "$src"/loop/analog/*.sv; do
    [ -f "$f" ] || continue
    cp "$f" "$dst/"; n=$((n + 1))
  done
  for f in "$src"/result.json; do
    [ -f "$f" ] || continue
    cp "$f" "$dst/"; n=$((n + 1))
  done
  # A hierarchical case is its blocks AND the top that composes them, so
  # name what must be there rather than counting to three. Three was
  # curate()'s floor for a single-block case; here it passed a PLL missing
  # every interface file, because the analog glob still said loop/ after
  # spice2rnm renamed that directory to cosim/.
  for want in netlist_top.sv result.json; do
    [ -f "$dst/$want" ] || { echo "curation for $2 has no $want"; exit 1; }
  done
  [ "$n" -ge 8 ] || { echo "curation for $2 found only $n file(s); expected the"\
                          " block models and the composed top"; exit 1; }
  echo "  $2: $n files"
}

echo "curating:"
# ---------------------------------------------------------------- equivalence
# The evidence behind each case study's equivalence figure.
#
# WHAT IS PUBLISHED AND WHAT IS NOT. The full traces are large -- the
# filter's aligned comparison is 18.6 MB and its generated testbench 18 MB,
# the duty corrector's waveform dump 11.7 MB, the interpolator's code sweep
# 14 MB: about 80 MB across four cases. Git history is permanent, and
# refresh.sh regenerates all of it in half an hour, so publishing it would
# cost every future clone that size forever in exchange for something a
# reader can produce themselves.
#
# So this publishes the part that cannot be regenerated from the models
# alone -- the simulator and SPICE logs that say what actually ran, and the
# verdict with its numbers -- plus a MANIFEST naming every file that was
# NOT published, with its size and where it comes from. A reader can see
# exactly what exists, what it weighs, and the command that recreates it.
curate_equivalence() {  # run-dir, dest-name, [subdir ...]
  local src="$1" name="$2"; shift 2
  local dst="$HERE/$name/equivalence"
  rm -rf "$dst"; mkdir -p "$dst"
  local man="$dst/MANIFEST.txt"
  {
    echo "Equivalence evidence for $name"
    echo
    echo "PUBLISHED HERE: the logs of what ran, and the verdict."
    echo "NOT PUBLISHED: the traces below. They are regenerated by"
    echo "  cd .. && ./refresh.sh          (about 34 minutes, all four cases)"
    echo
  } > "$man"
  local sub d f n=0
  for sub in "$@"; do
    d="$src/$sub"
    [ -d "$d" ] || continue
    for f in $(cd "$d" && find . -type f | sort); do
      case "$f" in
        *boundary.log|*xezim_cov.json)
          printf '  %10s  %s\n' "$(stat -c %s "$d/$f")" "$sub/${f#./}" >> "$man" ;;
        *.log|*ngspice.log|*.json)
          mkdir -p "$dst/$sub/$(dirname "$f")"
          cp "$d/$f" "$dst/$sub/$f"; n=$((n + 1)) ;;
        *)
          printf '  %10s  %s\n' "$(stat -c %s "$d/$f")" "$sub/${f#./}" >> "$man" ;;
      esac
    done
  done
  # The verdict itself, lifted from the run's own result.json rather than
  # retyped: a number in this directory that disagrees with the run that
  # produced it would be worse than no number.
  if [ -f "$src/result.json" ]; then
    python3 - "$src/result.json" > "$dst/verdict.txt" 2>/dev/null <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["result"]
def eq(e, label):
    if not isinstance(e, dict):
        return
    if not e.get("checked"):
        print("%-22s NOT CHECKED" % label); return
    print("%-22s %s  metric=%s  rms=%s  max=%s  threshold=%s"
          % (label, "PASS" if e.get("success") else "FAIL",
             e.get("metric"), e.get("rms_error_norm"),
             e.get("max_error_norm"), e.get("threshold")))
eq(r.get("equivalence"), "equivalence")
for row in r.get("block_results") or []:
    eq(((row.get("pipeline_result") or {}).get("equivalence")), row["block"]["name"])
for key in ("vco_results", "cp_results", "rc_results"):
    for nm, v in (r.get(key) or {}).items():
        eq(v.get("equivalence"), nm)
c = r.get("cosim_system_equivalence")
if isinstance(c, dict) and c.get("checked"):
    print("%-22s %s  boundary_samples=%s"
          % ("cosim system", c.get("verdict"), c.get("boundary_samples")))
PY
    [ -s "$dst/verdict.txt" ] || rm -f "$dst/verdict.txt"
  fi
  echo "  $name/equivalence: $n log(s), $(grep -c '^  ' "$man") trace(s) manifested"
}

curate lpf2      lpf2
curate dcc2      dcc2
curate demo3_pi  pi
curate_pll demo4_pll pll

echo "curating equivalence evidence:"
curate_equivalence "$HOME/s2r_runs/lpf2"     lpf2  equivalence
curate_equivalence "$HOME/s2r_runs/dcc2"     dcc2  equivalence
curate_equivalence "$HOME/s2r_runs/demo3_pi" pi    code_sweep
curate_equivalence "$HOME/s2r_runs/demo4_pll" pll \
    inv1/equivalence inv2/equivalence lpfilt/equivalence \
    ro_vco/_vco_equiv cpump/_cp_equiv cosim/model cosim/golden

# No generated file may point back at this machine or at product source
# files the customer does not have. This gate exists because both have
# happened; the generators were fixed, and this keeps them fixed.
leaks=$(grep -rln "/home/$(id -un)" "$HERE"/lpf2 "$HERE"/dcc2 "$HERE"/pi \
          "$HERE"/lpf2_house "$HERE"/pll \
          --include='*.sv' --include='*.svh' --include='*.sh' 2>/dev/null || true)
if [ -n "$leaks" ]; then
  echo "REFUSING to stamp: local paths leaked into generated files:"
  echo "$leaks" | sed 's/^/    /'
  exit 1
fi

# The simulator belongs in the stamp as much as the generator does. These
# artifacts are evidence, and evidence that cannot say which simulator
# produced it is weaker than it looks: the environments were once validated
# on one xezim revision while the tree moved on to another, and nothing here
# could have told you. Best effort -- a checkout may not be present.
XEZIM_BIN="${XEZIM:-$HOME/xezim/target/release/xezim}"
XEZIM_REPO="$(cd "$(dirname "$XEZIM_BIN")/../.." 2>/dev/null && pwd || true)"
xz_rev() {
  [ -n "${XEZIM_REPO:-}" ] && git -C "$XEZIM_REPO" rev-parse --short HEAD 2>/dev/null && return
  echo "unknown"
}
core_rev() {
  [ -n "${XEZIM_REPO:-}" ] && git -C "$XEZIM_REPO/../xezim-core" rev-parse --short HEAD 2>/dev/null && return
  echo "unknown"
}

{
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "spice2rnm: $(git -C "$HOME/spice2rnm" rev-parse --short HEAD)"
  echo "demos:     $(git -C "$DEMOS" rev-parse --short HEAD)"
  echo "xezim:     $(xz_rev)"
  echo "xezim-core: $(core_rev)"
  echo
  echo "Run summary:"
  sed 's/^/  /' /tmp/showcase_run_summary.txt
} > "$HERE/STAMP"
echo "stamped: $HERE/STAMP"
