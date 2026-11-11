`timescale 1ps/1ps
//======================================================================
// The system-level UVM-MS top.
//
// It instantiates the design's OWN testbench -- which brings the RTL, the
// stimulus and the bridge holding the composed analog models with it --
// and publishes the bridge's concrete proxy to the UVM environment, which
// is the handoff clause 4.2.1 describes.
//======================================================================
module top_pll_analog_sys_ms;

  import uvm_pkg::*;
  `include "uvm_macros.svh"
  import pll_analog_sys_proxy_pkg::*;
  import pll_analog_sys_ms_pkg::*;

  // The whole system: RTL + generated analog, exactly as the
  // co-simulation check already elaborates it.
  tb dut ();

  initial begin
    uvm_config_db #(pll_analog_sys_proxy)::set(null, "*", "bridge_proxy",
                                        dut.__ams_bridge.proxy);
    run_test("pll_analog_sys_test");
  end

  // The design's testbench calls $finish, which stops the simulation
  // before UVM's check and report phases. A final block still runs, so
  // the verdict is taken there rather than lost to a clean-looking exit.
  final begin
    if (pll_analog_sys_scoreboard::inst != null) begin
      pll_analog_sys_scoreboard::inst.do_check();
      pll_analog_sys_scoreboard::inst.do_report();
    end
    else
      $display("[top_pll_analog_sys_ms] NO SYSTEM VERDICT: no scoreboard was built");
  end

endmodule : top_pll_analog_sys_ms
