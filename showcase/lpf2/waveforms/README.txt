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
Score: rms error 0.67% of the circuit's swing (pass mark 15%), worst single point 1.8%: PASS.
How it was scored: rms of (model - circuit) on 4000 points from 416 ns (10 time constants of the slower pole), divided by the circuit's swing (0.8916 V). The model opens settled at the stimulus's first value as ngspice does, so the first 416 ns are left out only to match the window prbs_vcd.py and prbs_sweep2.py score.
Files: lpf2_prbs.fst, lpf2_prbs.gtkw, lpf2_prbs.svg, lpf2_prbs.html (0.2 MB of waveform; the page opens in any browser and zooms)

Full-range sweep with a chirp on top, through the two-pole RC filter
--------------------------------------------------------------------
Stimulus: the pipeline's own equivalence stimulus: a slow sweep from 0 V up to the top of the range and back, with a small chirp riding on it (a sine whose frequency slides upward through the filter's band), so one run exercises the whole input range and the whole band.
Score: rms error 0.07% of the circuit's swing (pass mark 15%), worst single point 0.6%: PASS.
How it was scored: rms of (model - circuit) over the whole run, divided by the circuit's swing (1.8087846 V), the pipeline's own equivalence check.
The two stretches where the model is furthest from the circuit (A and B in the picture) are both where the stimulus steps outside the 0..1.8 V input range the model was characterised over (it reaches -0.018..1.815 V). There the model holds its input at the edge of that range, the furthest it was measured, and filters it as usual, while the circuit keeps following the input; the error is that excess, smoothed by the filter, and only outside the measured range.
Files: lpf2_chirp.fst, lpf2_chirp.gtkw, lpf2_chirp.svg, lpf2_chirp.html (7.1 MB of waveform; the page opens in any browser and zooms)

Every trace and number above comes from one demo run's own output
files; nothing was re-simulated to make this folder.

The UVM-MS run (act 6), as waveforms
------------------------------------
lpf2_uvm.html: open it in any browser. It shows what the UVM-MS environment drove into the model, what came out, and at every scoreboard check what ngspice says the reading should be.
Verdicts: 49 DC checks and 15 AC checks against ngspice, 0 failed. Worst error: 37% of its tolerance.
Recorded by re-running the generated environment with three lines added to a copy of top_rc_lpf2_ms.sv; the checks are that run's own log lines. AC gains re-measured from the recording agree with the scoreboard's to within 2.1e-04 dB.
The bridge reads each AC sample at the middle of its drive step, so the phases carry no read bias of their own.

Not in this folder (over 1 MB, so kept out of git history): download
them from the repository's Releases page, tag waveforms-lpf2-<date>:
  lpf2_chirp.fst lpf2_chirp.gtkw
