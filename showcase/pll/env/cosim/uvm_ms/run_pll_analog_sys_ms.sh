#!/usr/bin/env bash
# Run the system UVM-MS environment: the design's RTL and the generated
# analog models in one elaboration, checked against the transistor run.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UVM=${UVM_SRC:-$HOME/iverilog-unified/uvm-core/src}
UVM_MS=${UVM_MS_LIB:-$HOME/uvm_ms_demo/ms}
XEZIM_BIN=${XEZIM:-$HOME/xezim/target/release/xezim}
for d in "$UVM/uvm_pkg.sv" "$UVM_MS/uvm_ms_pkg.sv"; do
  [ -f "$d" ] || { echo "ERROR: $d not found (set UVM_SRC / UVM_MS_LIB)." >&2; exit 1; }
done

# The generated models, found by NAME relative to this script rather
# than by the absolute path they happened to have when they were
# written. They sit in different places depending on how this
# environment is being used -- spread across the run directory as
# generated, flat beside the environment once published -- so the
# script looks in both instead of working in only one of them.
SEARCH="../analog ../../cpump ../../lpfilt ../../ro_vco ../../.. .. ."
[ -n "${S2R_MODELS:-}" ] && SEARCH="${S2R_MODELS} $SEARCH"
resolve() {
  local f="$1" d
  for d in $SEARCH; do
    if [ -f "$HERE/$d/$f" ]; then echo "$(cd "$HERE/$d" && pwd -P)/$f"; return 0; fi
  done
  echo "ERROR: cannot find '$f' near this script (looked in: $SEARCH)." >&2
  echo "       Set S2R_MODELS to the directory holding the models." >&2
  return 1
}

MODELS=()
for f in ams_node_pkg.sv cpump_cp_rnm.sv lpfilt_rc_rnm.sv ro_vco_rnm.sv cpump_iface.sv lpfilt_iface.sv ro_vco_iface.sv netlist_top.sv; do
  p="$(resolve "$f")" || exit 1
  MODELS+=("$p")
done

# The design's own RTL is not generated and is not published beside
# this environment, so there is nothing here to make it relative to.
RTL_DIR=${RTL_DIR:-$HOME/ams-cosim/examples/pll}
RTL=()
for f in pfd.sv divn.sv; do
  if [ ! -f "$RTL_DIR/$f" ]; then
    echo "ERROR: RTL file '$f' is not in '$RTL_DIR'." >&2
    echo "       Set RTL_DIR to the design's own RTL directory." >&2
    exit 1
  fi
  RTL+=("$RTL_DIR/$f")
done

exec "$XEZIM_BIN" --max-time 3us -DUVM_NO_DPI \
    -I "$UVM" -I "$UVM_MS" -I "$HERE" \
    "$UVM/uvm_pkg.sv" "$UVM_MS/uvm_ms_pkg.sv" \
    "${MODELS[@]}" "${RTL[@]}" \
    "$HERE/pll_analog_sys_proxy_pkg.sv" \
    "$HERE/pll_analog_sys_bridge.sv" \
    "$HERE/pll_analog_sys_ms_pkg.sv" \
    "$HERE/tb.sv" \
    "$HERE/top_pll_analog_sys_ms.sv" \
    +UVM_NO_RELNOTES
