#!/usr/bin/env bash
# Run the system UVM-MS environment: the design's RTL and the generated
# analog models in one elaboration, checked against the transistor run.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UVM=${UVM_SRC:-$HOME/iverilog-unified/uvm-core/src}
UVM_MS=${UVM_MS_LIB:-/home/vraje/uvm_ms_demo/ms}
XEZIM_BIN=${XEZIM:-/home/vraje/xezim/target/release/xezim}
for d in "$UVM/uvm_pkg.sv" "$UVM_MS/uvm_ms_pkg.sv"; do
  [ -f "$d" ] || { echo "ERROR: $d not found (set UVM_SRC / UVM_MS_LIB)." >&2; exit 1; }
done
exec "$XEZIM_BIN" --max-time 3us -DUVM_NO_DPI \
    -I "$UVM" -I "$UVM_MS" -I "$HERE" \
    "$UVM/uvm_pkg.sv" "$UVM_MS/uvm_ms_pkg.sv" \
    "/home/vraje/s2r_runs/pll_sys/cosim/analog/ams_node_pkg.sv" \
    "/home/vraje/s2r_runs/pll_sys/cpump/cpump_cp_rnm.sv" \
    "/home/vraje/s2r_runs/pll_sys/lpfilt/lpfilt_rc_rnm.sv" \
    "/home/vraje/s2r_runs/pll_sys/ro_vco/ro_vco_rnm.sv" \
    "/home/vraje/s2r_runs/pll_sys/cosim/analog/cpump_iface.sv" \
    "/home/vraje/s2r_runs/pll_sys/cosim/analog/lpfilt_iface.sv" \
    "/home/vraje/s2r_runs/pll_sys/cosim/analog/ro_vco_iface.sv" \
    "/home/vraje/s2r_runs/pll_sys/cosim/analog/netlist_top.sv" \
    "/home/vraje/ams-cosim/examples/pll/pfd.sv" \
    "/home/vraje/ams-cosim/examples/pll/divn.sv" \
    "$HERE/pll_analog_sys_proxy_pkg.sv" \
    "$HERE/pll_analog_sys_bridge.sv" \
    "$HERE/pll_analog_sys_ms_pkg.sv" \
    "$HERE/tb.sv" \
    "$HERE/top_pll_analog_sys_ms.sv" \
    +UVM_NO_RELNOTES
