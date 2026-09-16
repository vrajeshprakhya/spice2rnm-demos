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
  echo "generating the house-style case:"
  rm -rf "$HERE/lpf2_house"
  ( cd "$S2R" && python3 -m spice2rnm work/rc_lpf2.cir \
      --out-dir "$HERE/lpf2_house" \
      --input-node vin --output-node vout \
      --ngspice-bin "$NGSPICE" --sim xezim \
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
  for f in "$src"/loop/analog/*.sv; do
    [ -f "$f" ] || continue
    cp "$f" "$dst/"; n=$((n + 1))
  done
  for f in "$src"/result.json; do
    [ -f "$f" ] || continue
    cp "$f" "$dst/"; n=$((n + 1))
  done
  [ "$n" -ge 3 ] || { echo "curation for $2 found only $n file(s)"; exit 1; }
  echo "  $2: $n files"
}

echo "curating:"
curate lpf2      lpf2
curate dcc2      dcc2
curate demo3_pi  pi
curate_pll demo4_pll pll

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
