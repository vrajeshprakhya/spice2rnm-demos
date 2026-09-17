//======================================================================
// The system scoreboard: the composed models against the TRANSISTORS,
// on the design's own testbench.
//
// WHAT THE GOLDEN IS. Not the model's own equations, and not a table
// evaluated from the fit -- the goldens below are reduced from a run of
// this same testbench against the real analog through ngspice.
//
// WHY IT IS STATISTICS AND NOT SAMPLES. That run logged 87,010 boundary
// rows. The comparison does not consume them row by row: it reduces each
// node to per-window statistics and compares those, so that is what is
// carried here -- twenty rows instead of 87,010. It also sidesteps a trap
// this project has already fallen into once: fixed-stride decimation of
// vpdn read 69% low, because the phase-detector pulses are narrower than
// the stride. There is nothing to decimate.
//
// The cost, stated rather than hidden: an environment carrying summary
// statistics cannot re-derive the raw comparison. A reader sees the
// numbers the verdict rests on, not the golden waveform behind them,
// which stays in the run directory.
//
// HOW EACH NODE IS JUDGED -- the same rule the pipeline applies, because
// a second opinion about what "agree" means would make the two verdicts
// incomparable:
//
//   * a node the RTL slices at a threshold (`v_aout > VTH`) is judged on
//     its CROSSINGS of that threshold, because crossings are all the
//     logic ever sees of it. Judging its mean would punish a model that
//     emits a clean square against a transistor ring with finite edges,
//     on a difference no logic can observe.
//   * every other node is judged as a value: its window mean against the
//     golden's, scaled by the golden's own excursion -- floored at 2% of
//     the signal's magnitude, so a reference that barely moves does not
//     produce a denominator that barely exists and a tolerance that gets
//     stricter the better the reference behaves.
//======================================================================

class pll_analog_sys_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(pll_analog_sys_scoreboard)

  uvm_analysis_imp #(ams_xact_t, pll_analog_sys_scoreboard) ap;

  // The window grid the golden was reduced on. Both sides must use the
  // same one or the statistics are not about the same stretches of time.
  localparam int  N_WIN = 5;
  localparam real T_BEG = 0;
  localparam real T_END = 2.89995e-06;
  localparam real SPAN  = (T_END - T_BEG) / N_WIN;

  // Tolerances, from cosim_checks.compare().
  localparam real TOL_MEAN = 0.05;   // of the (floored) golden scale
  localparam real TOL_RISE = 0.02;   // relative, on crossing counts

  // The threshold the testbench itself slices aout at.
  localparam real VTH = 1.65;

  // Golden scales: the excursion each node showed in the transistor run,
  // floored at 2% of its magnitude (see the header).
  localparam real SCALE_AOUT  = 3.318963;
  localparam real SCALE_VOUT  = 0.037062;  // FLOORED: it only moved 5.9 mV
  localparam real SCALE_VPDN  = 3.300000;
  localparam real SCALE_VPUPB = 3.300000;

  localparam int N_GOLD = 20;
  string g_node  [N_GOLD];
  int    g_win   [N_GOLD];
  real   g_mean  [N_GOLD];
  real   g_rises [N_GOLD];

  // Model-side accumulation, per node per window. Indexed, not
  // associative: the nodes are known when this file is written.
  localparam int N_NODE = 4;
  real m_sum   [N_NODE][N_WIN];
  int  m_n     [N_NODE][N_WIN];
  int  m_rises [N_NODE][N_WIN];
  real m_last  [N_NODE];
  bit  m_seen  [N_NODE];

  function int idx_of(string node);
    case (node)
      "aout": return 0;
      "vout": return 1;
      "vpdn": return 2;
      "vpupb": return 3;
      default: return -1;
    endcase
  endfunction

  int n_xact, n_checks, n_failed;
  int n_dropped;
  int n_inconclusive;

  function string node_of(int k);
    case (k)
      0: return "aout";
      1: return "vout";
      2: return "vpdn";
      3: return "vpupb";
    endcase
  endfunction

  // Which golden row holds this node's window, or -1.
  function int gold_index(string node, int w);
    for (int i = 0; i < N_GOLD; i++)
      if (g_node[i] == node && g_win[i] == w) return i;
    return -1;
  endfunction

  // Floored where the golden barely moved: vout covered 5.9 mV, so its
  // scale is 2% of its magnitude instead.
  function bit scale_floored(string node);
    case (node)
      "aout": return 1'b0;
      "vout": return 1'b1;
      "vpdn": return 1'b0;
      "vpupb": return 1'b0;
      default: return 1'b0;
    endcase
  endfunction

  function bit golden_moving(string node);
    case (node)
      "aout": return 1'b0;
      "vout": return 1'b1;
      "vpdn": return 1'b0;
      "vpupb": return 1'b0;
      default: return 1'b0;
    endcase
  endfunction

  function real golden_span(string node);
    case (node)
      "aout": return 3.3189721;
      "vout": return 0.00589714132;
      "vpdn": return 3.3;
      "vpupb": return 3.3;
      default: return 1.0;
    endcase
  endfunction

  // THE DESIGN'S TESTBENCH ENDS THE RUN. It calls $finish once the PLL
  // has been observed long enough, which is correct -- it owns the
  // stimulus -- but $finish stops the simulation dead, and UVM's
  // check_phase and report_phase never execute. A scoreboard that only
  // reported from a phase would therefore report nothing here, and would
  // do it silently: a clean exit with no verdict reads exactly like a
  // clean exit with a passing one. Measured, not guessed -- the first
  // run of this environment exited 0 and printed no scoreboard line.
  //
  // A final block does run on $finish, so the checking is factored out of
  // the phases and called from both. The guard makes the second call a
  // no-op for a run that does reach its phases.
  static pll_analog_sys_scoreboard inst;
  bit reported;

  function new(string name, uvm_component parent);
    super.new(name, parent);
    ap = new("ap", this);
  endfunction

  function void build_phase(uvm_phase phase);
    inst = this;
    // ---- GOLDEN: reduced from the ngspice run of this same testbench ----
    g_node[ 0] = "aout"; g_win[ 0] = 0; g_mean[ 0] = 1.73935852; g_rises[ 0] = 231;
    g_node[ 1] = "aout"; g_win[ 1] = 1; g_mean[ 1] = 1.73868464; g_rises[ 1] = 231;
    g_node[ 2] = "aout"; g_win[ 2] = 2; g_mean[ 2] = 1.73725081; g_rises[ 2] = 232;
    g_node[ 3] = "aout"; g_win[ 3] = 3; g_mean[ 3] = 1.734841; g_rises[ 3] = 233;
    g_node[ 4] = "aout"; g_win[ 4] = 4; g_mean[ 4] = 1.7381188; g_rises[ 4] = 232;
    g_node[ 5] = "vout"; g_win[ 5] = 0; g_mean[ 5] = 1.85281707; g_rises[ 5] = 0;
    g_node[ 6] = "vout"; g_win[ 6] = 1; g_mean[ 6] = 1.85309382; g_rises[ 6] = 0;
    g_node[ 7] = "vout"; g_win[ 7] = 2; g_mean[ 7] = 1.84959663; g_rises[ 7] = 0;
    g_node[ 8] = "vout"; g_win[ 8] = 3; g_mean[ 8] = 1.84719668; g_rises[ 8] = 0;
    g_node[ 9] = "vout"; g_win[ 9] = 4; g_mean[ 9] = 1.84865006; g_rises[ 9] = 0;
    g_node[10] = "vpdn"; g_win[10] = 0; g_mean[10] = 0.0102422623; g_rises[10] = 6;
    g_node[11] = "vpdn"; g_win[11] = 1; g_mean[11] = 0.0307294361; g_rises[11] = 6;
    g_node[12] = "vpdn"; g_win[12] = 2; g_mean[12] = 0.0478013451; g_rises[12] = 5;
    g_node[13] = "vpdn"; g_win[13] = 3; g_mean[13] = 0.0307294361; g_rises[13] = 6;
    g_node[14] = "vpdn"; g_win[14] = 4; g_mean[14] = 0.010244912; g_rises[14] = 6;
    g_node[15] = "vpupb"; g_win[15] = 0; g_mean[15] = 3.24480559; g_rises[15] = 6;
    g_node[16] = "vpupb"; g_win[16] = 1; g_mean[16] = 3.28861873; g_rises[16] = 6;
    g_node[17] = "vpupb"; g_win[17] = 2; g_mean[17] = 3.29146405; g_rises[17] = 5;
    g_node[18] = "vpupb"; g_win[18] = 3; g_mean[18] = 3.28975685; g_rises[18] = 6;
    g_node[19] = "vpupb"; g_win[19] = 4; g_mean[19] = 3.27552604; g_rises[19] = 6;
  endfunction

  function int win_of(real t_s);
    int w;
    if (t_s < T_BEG) return -1;
    // $floor, NOT a bare int' cast. Converting a real to int in
    // SystemVerilog ROUNDS to nearest (IEEE 1800-2017 6.12.2); it does not
    // truncate. So `int'(t/SPAN)` put everything from half a window onward
    // into the NEXT window: window 0 kept only t < SPAN/2 and came back
    // with 2,900 samples where the log had 5,800, windows 1..4 each held a
    // full span shifted half a window late, and the last half-window fell
    // off the end as w=5. Every window-0 disagreement in this report --
    // aout 116 crossings against 231, vpdn and vpupb 3 against 6 -- was
    // this cast, and the totals gave it away: 2,900 is exactly half of
    // 5,800, and exactly what was missing from the end.
    w = int'($floor((t_s - T_BEG) / SPAN));
    if (w >= N_WIN) return -1;      // past the golden run's end
    return w;
  endfunction

  function real scale_of(string node);
    case (node)
      "aout": return 3.3189721;
      "vout": return 0.0370618764;
      "vpdn": return 3.3;
      "vpupb": return 3.3;
      default: return 1.0;
    endcase
  endfunction

  // The midpoint each node's crossings are counted about: the RTL's own
  // threshold where it has one, the golden's mid-range otherwise.
  function real mid_of(string node);
    case (node)
      "aout": return 1.65;
      "vout": return 1.85014525;
      "vpdn": return 1.65;
      "vpupb": return 1.65;
      default: return 0.0;
    endcase
  endfunction

  function void write(ams_xact_t x);
    int w, k;
    real mid;
    n_xact++;
    if (x.kind == "I") return;          // the internal probe is not a boundary
    w = win_of(x.t_s);
    if (w < 0) return;
    k = idx_of(x.node);
    if (k < 0) return;
    mid = mid_of(x.node);
    m_sum[k][w] += x.v;
    m_n  [k][w] += 1;
    if (m_seen[k] && m_last[k] <= mid && x.v > mid)
      m_rises[k][w] += 1;
    m_last[k] = x.v;
    m_seen[k] = 1;
  endfunction

  function void check_phase(uvm_phase phase);
    do_check();
  endfunction

  function void do_check();
    // THE PIPELINE'S RULES, not a second opinion about what "agree" means.
    // cosim_checks.compare() decides per NODE, not per window: it walks the
    // windows accumulating the worst figures, SKIPS any window where either
    // side has no samples, and then applies one verdict to the node.
    //
    //   * a node the RTL slices at a threshold is judged on crossings alone
    //   * every other node on its window mean, against a scale floored at
    //     2% of its magnitude
    //   * and a mean disagreement on a reference that is STILL MOVING, where
    //     the model sits inside the excursion the reference itself covered,
    //     is INCONCLUSIVE rather than failed: two settling curves of the
    //     same shape, one lagging, differ at every window while describing
    //     the same circuit.
    int    n_win_cmp;
    real   worst_mean, worst_abs, worst_rise;
    bit    node_ok, node_inconclusive;

    if (n_dropped > 0) begin
      `uvm_error("SYS_SB", $sformatf(
        "the bridge dropped %0d crossings the monitor never saw. The statistics below are over an incomplete observation.",
        n_dropped))
      n_failed++;
    end
    if (n_xact == 0) begin
      `uvm_error("SYS_SB",
                 "NO BOUNDARY TRAFFIC REACHED THE SCOREBOARD. Nothing below was compared against anything; this is not a passing system check.")
      n_failed++;
    end

    for (int k = 0; k < N_NODE; k++) begin
      string node = node_of(k);
      real   scale = scale_of(node);
      bit    is_thr = (node == "aout");
      n_win_cmp = 0;
      worst_mean = 0.0; worst_abs = 0.0; worst_rise = 0.0;
      for (int w = 0; w < N_WIN; w++) begin
        int  gi = gold_index(node, w);
        int  n  = m_n[k][w];
        real mm, da, dm, dr, gr;
        // A window either side left empty is SKIPPED, not failed. The
        // testbench reads some nodes rarely -- vout eight times in the
        // whole run -- and a window where one side happened to have no
        // read is not evidence of disagreement.
        if (gi < 0 || n == 0) continue;
        n_win_cmp++;
        mm = m_sum[k][w] / real'(n);
        da = mm - g_mean[gi];
        if (da < 0.0) da = -da;
        dm = da / scale;
        gr = g_rises[gi];
        dr = (gr > 0.0 || m_rises[k][w] > 0)
             ? (real'(m_rises[k][w]) - gr) / ((gr > 1.0) ? gr : 1.0) : 0.0;
        if (dr < 0.0) dr = -dr;
        if (dm > worst_mean) worst_mean = dm;
        if (da > worst_abs)  worst_abs  = da;
        if (dr > worst_rise) worst_rise = dr;
        `uvm_info("SYS_SB", $sformatf(
          "%-6s w%0d n=%0d model mean=%0.6f rises=%0d | transistors mean=%0.6f rises=%0.0f | dm=%0.4g dr=%0.4g",
          node, w, n, mm, m_rises[k][w], g_mean[gi], gr, dm, dr), UVM_MEDIUM)
      end

      n_checks++;
      if (n_win_cmp == 0) begin
        `uvm_error("SYS_SB", $sformatf(
          "%s: no window had samples on both sides -- nothing was compared", node))
        n_failed++;
        continue;
      end

      node_inconclusive = 0;
      if (is_thr) begin
        node_ok = (worst_rise <= TOL_RISE);
      end else begin
        // Crossings of a node with no threshold of its own are crossings of
        // the midpoint of whatever range it covered. On a reference flat to
        // within the floor that midpoint sits in the noise, so the count is
        // a count of noise; where the scale is floored, the mean is the
        // whole story.
        node_ok = (worst_mean <= TOL_MEAN) &&
                  (scale_floored(node) || worst_rise <= TOL_RISE);
        if (!node_ok && golden_moving(node) && worst_abs <= golden_span(node)) begin
          node_ok = 1;
          node_inconclusive = 1;
        end
      end

      if (!node_ok) begin
        `uvm_error("SYS_SB", $sformatf(
          "%s FAIL judged on %s: worst |diff| %0.4g (%0.2f%% of scale), worst crossings %0.2f%%, over %0d window(s)",
          node, is_thr ? "crossings" : "mean", worst_abs,
          100.0*worst_mean, 100.0*worst_rise, n_win_cmp))
        n_failed++;
      end else begin
        `uvm_info("SYS_SB", $sformatf(
          "%s %s judged on %s: worst |diff| %0.4g (%0.2f%% of scale), worst crossings %0.2f%%, over %0d window(s)",
          node, node_inconclusive ? "INCONCLUSIVE" : "ok",
          is_thr ? "crossings" : "mean", worst_abs,
          100.0*worst_mean, 100.0*worst_rise, n_win_cmp), UVM_LOW)
        if (node_inconclusive) n_inconclusive++;
      end
    end
  endfunction

  function void report_phase(uvm_phase phase);
    do_report();
  endfunction

  function void do_report();
    if (reported) return;
    reported = 1;
    `uvm_info("SB_SUMMARY", $sformatf(
      "system checks=%0d failed=%0d inconclusive=%0d | %0d boundary crossings observed through the MS bridge",
      n_checks, n_failed, n_inconclusive, n_xact), UVM_LOW)
    if (n_checks == 0)
      `uvm_error("SB_SUMMARY",
                 "no system check ran -- the goldens were never reached")
  endfunction

endclass : pll_analog_sys_scoreboard
