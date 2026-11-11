`timescale 1ps/1ps
//======================================================================
// The ABSTRACT half of the system MS Proxy (UVM-MS clause 4.2.1).
//
// The API is the ten DPI functions the co-simulation already crosses the
// analog/digital boundary with, reduced to push/pull/monitor. Clause
// 4.2.1 lists exactly those three plus push-sync as a typical proxy API.
//======================================================================
package pll_analog_sys_proxy_pkg;

  import uvm_pkg::*;
  import uvm_ms_pkg::*;
  `include "uvm_macros.svh"

  virtual class pll_analog_sys_proxy extends uvm_ms_proxy;

    function new(string name = "pll_analog_sys_proxy");
      super.new(name);
    endfunction

    // 6.2.4 push -- drive one of the sources the netlist declares external.
    pure virtual function void push_source(input string node, input real v);

    // 6.2.6 pull -- read one of the nodes the partition exposes.
    pure virtual function real pull_node(input string node);
    pure virtual function real pull_dra();

    // The period jitter the boundary actually shows, measured at 1 fs by
    // monitors inside the bridge. A pull like any other, so the
    // scoreboard needs no hierarchical path into the design.
    pure virtual function string pull_jitter();

    // 4.2.1 "Monitor continuous signals". The monitor observes what
    // actually crosses the bridge, at the instants it crosses, rather
    // than sampling on a grid of its own choosing. That is not a style
    // preference: this testbench ticks the analog every 100 ps because
    // the ring runs near 400 MHz, and the file says what a 1 ns grid
    // does to it -- 199 edges over 1600 ns reads as a confident 124 MHz.
    // A monitor with its own clock would measure its own aliasing.
    pure virtual task wait_xact();
    // Readable, so a monitor that sees nothing can tell whether nothing
    // crossed or whether it simply failed to wake.
    pure virtual function int xact_count();
    // The latched value of one boundary node, and the time now. Sampled
    // together so the monitor observes all of the boundary at each tick
    // rather than whichever crossing happened to be last.
    pure virtual function bit next_xact(output string kind,
                                        output string node,
                                        output real   v,
                                        output real   t_s);
    // Crossings the bridge could not hold. A monitor that cannot say
    // whether it saw everything is not evidence about anything.
    pure virtual function int dropped_count();
    pure virtual function void get_xact(output string kind,
                                        output string node,
                                        output real   v,
                                        output real   t_s);

  endclass : pll_analog_sys_proxy

endpackage : pll_analog_sys_proxy_pkg
