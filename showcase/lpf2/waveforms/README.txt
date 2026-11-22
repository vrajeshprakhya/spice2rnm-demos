lpf2: the circuit and its model, side by side
============================================================

Each stimulus has four files:
  *.html  the waveforms as a web page: open it in any browser and
          drag across the plot to zoom (nothing to install)
  *.svg   the same comparison as a still picture
  *.fst   the waveforms for a waveform viewer (GTKWave, Surfer)
  *.gtkw  a GTKWave layout that draws them as curves

Open one in GTKWave from this folder:
  gtkwave lpf2_prbs.fst lpf2_prbs.gtkw

Signals (all in volts):
  vin           the stimulus driving the filter input, volts
  vout_circuit  the circuit's output, solved by ngspice, volts
  vout_model    the model's output, simulated by xezim, volts
  error         vout_model - vout_circuit, volts

PRBS7 at 160 Mb/s through the two-pole RC filter
------------------------------------------------
Stimulus: binary data: a PRBS7 bit pattern at 160 Mb/s, which the model was NOT fitted from; the filter's slow edges smear each bit into the next (inter-symbol interference).
Score: rms error 0.97% of the circuit's swing (pass mark 15%), worst single point 2.3%: PASS.
How it was scored: rms of (model - circuit) on 4000 points from 416 ns, divided by the circuit's swing (0.8916 V). Before 416 ns the model is still waking up from rest while ngspice starts already settled, so that stretch compares two starting points, not two filters, and is not scored.
Files: lpf2_prbs.fst, lpf2_prbs.gtkw, lpf2_prbs.svg, lpf2_prbs.html (0.2 MB of waveform; the page opens in any browser and zooms)

Full-range sweep with a chirp on top, through the two-pole RC filter
--------------------------------------------------------------------
Stimulus: the pipeline's own equivalence stimulus: a slow sweep from 0 V up to the top of the range and back, with a small chirp riding on it (a sine whose frequency slides upward through the filter's band), so one run exercises the whole input range and the whole band.
Score: rms error 2.90% of the circuit's swing (pass mark 15%), worst single point 49.8%: PASS.
How it was scored: rms of (model - circuit) over the whole run, divided by the circuit's swing (1.8087846 V), the pipeline's own equivalence check.
After start-up (from 416 ns): rms 0.11%, worst point 0.99%. The model's output begins at mid-scale (0.90 V, while the circuit sits at 0.00 V) and takes until 170 ns to come within 1% of the circuit, and the whole-run figures include that.
The two stretches where the settled model is furthest from the circuit (A and B in the picture) are both where the stimulus steps outside the 0..1.8 V input range the model was characterised over (it reaches -0.018..1.815 V). There the model adds clamp(input) - input straight onto its output, outside its filter (rc_lpf2_rnm.sv, final_out = static_out + (dynamic_out - GAIN_DC*u_dev)), so the output jumps by the input's excess instantly, sharp corners included, which no RC filter can do. The error in those stretches is that excess, sample for sample: a property of where the model applies its clamp, not of its filter, and only outside the measured range.
Files: lpf2_chirp.fst, lpf2_chirp.gtkw, lpf2_chirp.svg, lpf2_chirp.html (7.2 MB of waveform; the page opens in any browser and zooms)

Every trace and number above comes from one demo run's own output
files; nothing was re-simulated to make this folder.

The UVM-MS run (act 6), as waveforms
------------------------------------
lpf2_uvm.html: open it in any browser. It shows what the UVM-MS environment drove into the model, what came out, and at every scoreboard check what ngspice says the reading should be.
Verdicts: 49 DC checks and 15 AC checks against ngspice, 0 failed. Worst error: 34% of its tolerance.
Recorded by re-running the generated environment with three lines added to a copy of top_rc_lpf2_ms.sv; the checks are that run's own log lines. AC gains re-measured from the recording agree with the scoreboard's to within 7.7e-05 dB.
Caution: the bridge reads each AC sample at the end of a drive step but scores it against the phase at the step's start, a lead of about 2.8 deg included in every phase error.

Not in this folder (over 1 MB, so kept out of git history): download
them from the repository's Releases page, tag waveforms-lpf2-<date>:
  lpf2_chirp.fst lpf2_chirp.gtkw
