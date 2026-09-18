`timescale 1ps/1ps
//======================================================================
// The system MS BRIDGE (UVM-MS clause 4.2).
//
// It holds the composed analog top -- every block replaced by its
// generated model -- and the concrete proxy through which a UVM-MS agent
// reaches it. This is the boundary the co-simulation already has: the
// netlist declares two sources `external`, and the design's testbench
// crosses to the analog through exactly ten DPI functions. Those ten are
// what the proxy API replaces, so no wiring has to be inferred.
//======================================================================
module pll_analog_sys_bridge;

  import uvm_pkg::*;
  import uvm_ms_pkg::*;
  `include "uvm_macros.svh"
  `include "uvm_ms_includes.svh"

  import pll_analog_sys_proxy_pkg::*;

  localparam real SEC_PER_TICK = 1.0e-12;

  // The analog/digital boundary, as the netlist declares it.
  logic  __ams_l_pdn = 1'b0;
  logic  __ams_l_pupb = 1'b0;
  real   __ams_n_aout_v;
  real   __ams_n_vout_v;

  analog_top core (.pdn(__ams_l_pdn), .pupb(__ams_l_pupb), .aout_v(__ams_n_aout_v), .vout_v(__ams_n_vout_v));

  // PERIOD JITTER, measured at 1 fs. These monitors are compiled at a
  // finer timescale than the rest of this environment on purpose: a
  // crossing recorded on the picosecond grid everything else uses cannot
  // be located to better than a picosecond, and the figures worth having
  // here are tenths of one.
  // aout is judged on crossings, so it has periods to measure.
  pll_analog_sys_jitter #(.VTH(1.65)) jit_aout (.sig(__ams_n_aout_v));

  // PRINTED FROM `final`, not from a UVM phase. The design's own
  // testbench calls $finish, and $finish skips check_phase and
  // report_phase -- which is why the scoreboard's verdict was moved into
  // a final block with a static handle. The first version of this report
  // sat in the monitor's report_phase and produced nothing at all: no
  // error, no empty measurement, no mention of the monitor anywhere in
  // the log.
  final begin
    if (jitter_report().len() > 0) begin
      $display("[SYS_JITTER] period jitter at the boundary, measured at 1 fs");
      $display("[SYS_JITTER]   reported, not judged: a loop suppresses its");
      $display("[SYS_JITTER]   oscillator's jitter inside the loop bandwidth,");
      $display("[SYS_JITTER]   so this is not the block's jitter and the two");
      $display("[SYS_JITTER]   are not expected to agree.");
      $write("%s", jitter_report());
    end
  end

  // Built here rather than in the scoreboard because the monitors are
  // here. A class reaching a module instance needs a hierarchical path,
  // and a path stops matching the moment anything above it is renamed.
  function automatic string jitter_report();
    string out, l;
    out = "";
      $sformat(l, "aout: %0d periods, mean %0.6f ns, rms jitter %0.4f ps, pk-pk %0.4f ps", jit_aout.periods(), jit_aout.mean_period()*1.0e9, jit_aout.rms_jitter()*1.0e12, jit_aout.pk_pk()*1.0e12);
      out = {out, l, "\n"};
    return out;
  endfunction

  // Every crossing, recorded as it happens. The monitor observes these.
  string   x_kind, x_node;
  real     x_v, x_t;
  // A counter, not a named event: the event form triggered from inside a
  // function reached no waiting process here, and an event that does not
  // arrive leaves nothing to inspect. A counter can be read.
  int      x_seq;
  // A ring buffer of crossings, drained by the monitor.
  // Deep enough to bridge the gap between time zero and the monitor's
  // first drain. The design's testbench runs from t=0; a UVM run_phase
  // starts only after build, connect and end_of_elaboration, and the
  // crossings in between are real traffic that has to be held rather
  // than lost. Measured at 256: the first window came back with 2,900
  // samples where every other window had 5,800, and EVERY window-0
  // disagreement in the report was that missing half -- aout 116
  // crossings against 231, vpdn and vpupb 3 against 6, vout absent
  // entirely. None of it was about the models.
  localparam int QDEPTH = 65536;
  string   q_kind [QDEPTH];
  string   q_node [QDEPTH];
  real     q_v    [QDEPTH];
  real     q_t    [QDEPTH];
  int      q_wr;        // crossings recorded
  int      q_rd;        // crossings handed to the monitor
  int      q_dropped;   // crossings lost to overflow -- reported, never hidden

  function automatic void note(input string kind, input string node,
                               input real v);
    x_kind = kind;
    x_node = node;
    x_v    = v;
    x_t    = $realtime * SEC_PER_TICK;
    if ((q_wr - q_rd) >= QDEPTH) begin
      q_dropped++;
    end else begin
      q_kind[q_wr % QDEPTH] = kind;
      q_node[q_wr % QDEPTH] = node;
      q_v   [q_wr % QDEPTH] = v;
      q_t   [q_wr % QDEPTH] = $realtime * SEC_PER_TICK;
      q_wr++;
    end
    x_seq++;
  endfunction

  // Thresholds are the DESIGN's, carried over from the harness rather
  // than chosen here: a bridge that picked its own would be a second
  // opinion about where logic one begins.
  function automatic void apply(input string node, input real v);
    case (node)
      "vpdn": __ams_l_pdn = (v > 1.65);
      "vpupb": __ams_l_pupb = (v > 1.65);
      default: $display("[spice2rnm harness] ams_set(%s): not a source this partition declares external", node);
    endcase
    note("S", node, v);
  endfunction

  function automatic real read_raw(input string node);
    case (node)
      "aout": return __ams_n_aout_v;
      "vout": return __ams_n_vout_v;
      default: begin
        $display("[spice2rnm harness] ams_get(%s): not a node the partition exposes", node);
        return 0.0;
      end
    endcase
  endfunction

  function automatic real read(input string node);
    real v;
    v = read_raw(node);
    note("G", node, v);
    return v;
  endfunction

    function automatic void probe();
    note("I", "dra", core.dra_v);
  endfunction

  //--------------------------------------------------------------------
  // The concrete proxy (clause 4.2.1): declared in the bridge, handed to
  // the agent as the abstract type through uvm_config_db.
  //--------------------------------------------------------------------
  class MSproxy extends pll_analog_sys_proxy;
    function new(string name = "proxy");
      super.new(name);
    endfunction
    virtual function void push_source(input string node, input real v);
      apply(node, v);
    endfunction
    virtual function real pull_node(input string node);
      return read(node);
    endfunction
    virtual function real pull_dra();
      return read_dra();
    endfunction
    virtual function string pull_jitter();
      return jitter_report();
    endfunction
    virtual task wait_xact();
      @(x_seq);
    endtask
    virtual function int xact_count();
      return x_seq;
    endfunction
    // Hand over the next recorded crossing, oldest first. Returns 0 when
    // the buffer is empty, so the monitor drains with a while loop and
    // cannot mistake "nothing left" for "nothing happened".
    virtual function bit next_xact(output string kind, output string node,
                                   output real v, output real t_s);
      if (q_rd >= q_wr) return 1'b0;
      kind = q_kind[q_rd % QDEPTH];
      node = q_node[q_rd % QDEPTH];
      v    = q_v   [q_rd % QDEPTH];
      t_s  = q_t   [q_rd % QDEPTH];
      q_rd++;
      return 1'b1;
    endfunction
    virtual function int dropped_count();
      return q_dropped;
    endfunction
    virtual function void get_xact(output string kind, output string node,
                                   output real v, output real t_s);
      kind = x_kind;
      node = x_node;
      v    = x_v;
      t_s  = x_t;
    endfunction
  endclass : MSproxy

  MSproxy proxy = new("proxy");

endmodule : pll_analog_sys_bridge
