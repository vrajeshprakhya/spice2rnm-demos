`timescale 1ps/1ps
//======================================================================
// A UVM-MS environment over the WHOLE system: the design's RTL and the
// generated analog models in one elaboration, checked against a run of
// the same testbench against the transistors.
//
// The agent is passive by construction. The stimulus is the design's
// own -- its testbench makes it, and every crossing uses the testbench's
// own thresholds and expressions. A driver here would be a second
// opinion about how the system is exercised, and the two runs would stop
// being comparable. So the monitor observes, and the scoreboard judges.
//======================================================================
package pll_analog_sys_ms_pkg;

  import uvm_pkg::*;
  import uvm_ms_pkg::*;
  `include "uvm_macros.svh"
  import pll_analog_sys_proxy_pkg::*;

  // One crossing of the analog/digital boundary.
  typedef struct {
    string kind;   // "S" driven into the analog, "G" read out, "I" probe
    string node;
    real   v;
    real   t_s;
  } ams_xact_t;

  `include "pll_analog_sys_ms_scoreboard.svh"

  //--------------------------------------------------------------------
  class pll_analog_sys_monitor extends uvm_monitor;
    `uvm_component_utils(pll_analog_sys_monitor)

    pll_analog_sys_proxy bp;
    uvm_analysis_port #(ams_xact_t) ap;
    int n_seen;

    function new(string name, uvm_component parent);
      super.new(name, parent);
      ap = new("ap", this);
    endfunction

    function void build_phase(uvm_phase phase);
      if (!uvm_config_db #(pll_analog_sys_proxy)::get(this, "", "bridge_proxy", bp))
        `uvm_fatal("NOPROXY",
                   "no bridge proxy in uvm_config_db -- the bridge is not reachable")
    endfunction

    task run_phase(uvm_phase phase);
      ams_xact_t x;
      forever begin
        bp.wait_xact();
        // Drain, rather than sample. Several crossings happen inside one
        // tick and a process wakes once per tick, so anything that reads
        // a single slot per wake loses the rest.
        while (bp.next_xact(x.kind, x.node, x.v, x.t_s)) begin
          n_seen++;
          ap.write(x);
        end
        if (pll_analog_sys_scoreboard::inst != null)
          pll_analog_sys_scoreboard::inst.n_dropped = bp.dropped_count();
      end
    endtask

    function void report_phase(uvm_phase phase);
      string jr;
      if (n_seen == 0)
        `uvm_error("SYS_MON",
                   "the monitor saw no boundary traffic -- the proxy was reachable but nothing crossed")

      // PERIOD JITTER AT THE BOUNDARY, measured by monitors compiled at
      // 1 fs inside the bridge. Everything else in this environment runs
      // on a picosecond grid, which cannot locate an edge to better than
      // a picosecond -- and the figures worth having here are tenths of
      // one.
      //
      // REPORTED, NOT JUDGED, and the reason is the design rather than a
      // missing feature: a loop SUPPRESSES its oscillator's jitter inside
      // the loop bandwidth, so the jitter seen here is not the jitter the
      // block produces and the two are not expected to agree. That is the
      // loop working. A pass/fail needs a bound somebody states; inventing
      // one from a single design would be worse than showing the number.
      // The bridge prints this from a `final` block as well, and that
      // is the copy to rely on: the design's testbench calls $finish,
      // which skips this phase entirely. This one appears only when the
      // run ends some other way.
      jr = bp.pull_jitter();
      if (jr.len() > 0)
        `uvm_info("SYS_JITTER",
                  {"period jitter at the boundary, measured at 1 fs ",
                   "(reported, not judged -- see the note in the bridge):\n",
                   jr}, UVM_LOW)
    endfunction
  endclass : pll_analog_sys_monitor

  //--------------------------------------------------------------------
  class pll_analog_sys_agent extends uvm_agent;
    `uvm_component_utils(pll_analog_sys_agent)

    pll_analog_sys_monitor mon;

    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      // PASSIVE, and not by default: the design's testbench supplies the
      // stimulus. An active agent would drive the system differently from
      // the run its goldens came from.
      if (!uvm_config_db #(uvm_active_passive_enum)::get(this, "", "is_active", is_active))
        is_active = UVM_PASSIVE;
      if (is_active == UVM_ACTIVE)
        `uvm_fatal("SYS_AGENT",
                   "this agent has no driver or sequencer, and cannot have one: the stimulus belongs to the design's own testbench, and driving it from here would make this run incomparable to the transistor run its goldens come from")
      mon = pll_analog_sys_monitor::type_id::create("mon", this);
    endfunction
  endclass : pll_analog_sys_agent

  class pll_analog_sys_env extends uvm_env;
    `uvm_component_utils(pll_analog_sys_env)
    pll_analog_sys_agent      agent;
    pll_analog_sys_scoreboard sb;
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    function void build_phase(uvm_phase phase);
      agent = pll_analog_sys_agent::type_id::create("agent", this);
      sb    = pll_analog_sys_scoreboard::type_id::create("sb", this);
    endfunction
    function void connect_phase(uvm_phase phase);
      agent.mon.ap.connect(sb.ap);
    endfunction
  endclass : pll_analog_sys_env

  //--------------------------------------------------------------------
  class pll_analog_sys_test extends uvm_test;
    `uvm_component_utils(pll_analog_sys_test)
    pll_analog_sys_env env;
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    function void build_phase(uvm_phase phase);
      env = pll_analog_sys_env::type_id::create("env", this);
    endfunction
    task run_phase(uvm_phase phase);
      // The design's own testbench supplies the stimulus and ends the
      // run; this objection only keeps UVM alive alongside it, for the
      // span the goldens cover.
      phase.raise_objection(this);
      #2899950;   // 2.89995 us in ps -- the golden run's own span
      phase.drop_objection(this);
    endtask
  endclass : pll_analog_sys_test

endpackage : pll_analog_sys_ms_pkg
