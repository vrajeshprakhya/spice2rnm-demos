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

echo "curating:"
curate lpf2      lpf2
curate dcc2      dcc2
curate demo3_pi  pi

# No generated file may point back at this machine or at product source
# files the customer does not have. This gate exists because both have
# happened; the generators were fixed, and this keeps them fixed.
leaks=$(grep -rln "/home/$(id -un)" "$HERE"/lpf2 "$HERE"/dcc2 "$HERE"/pi \
          --include='*.sv' --include='*.svh' --include='*.sh' 2>/dev/null || true)
if [ -n "$leaks" ]; then
  echo "REFUSING to stamp: local paths leaked into generated files:"
  echo "$leaks" | sed 's/^/    /'
  exit 1
fi

{
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "spice2rnm: $(git -C "$HOME/spice2rnm" rev-parse --short HEAD)"
  echo "demos:     $(git -C "$DEMOS" rev-parse --short HEAD)"
  echo
  echo "Run summary:"
  sed 's/^/  /' /tmp/showcase_run_summary.txt
} > "$HERE/STAMP"
echo "stamped: $HERE/STAMP"
