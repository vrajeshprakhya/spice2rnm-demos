pll_nocosim: demo 4b's PLL as waveforms
============================================================

Open any .html file in a browser and drag across a plot to zoom.
The data is inside each page; nothing to install.

pll_nocosim_loop.html
  The whole loop over the demo's whole run: generated models for
  the analog blocks, the design's own RTL for the phase detector
  and divider, on one simulator. No transistors.
  Locked: the divided clock runs at 10.001704 MHz against 10.001401 MHz asked for (+0.0030%, tolerance 2%), and the control voltage moved 0.192 mV across the measured window. Generated models around the design's own RTL: no transistors in this run.

pll_nocosim_inv1.html  (and pll_nocosim_inv1.fst, pll_nocosim_inv1.gtkw for GTKWave)
  An inverter, circuit (ngspice) against model (xezim).
  rms error 2.08% of the circuit's swing (pass mark 15%), worst single point 99.9%: PASS

pll_nocosim_inv2.html  (and pll_nocosim_inv2.fst, pll_nocosim_inv2.gtkw for GTKWave)
  An inverter, circuit (ngspice) against model (xezim).
  rms error 2.17% of the circuit's swing (pass mark 15%), worst single point 17.6%: PASS

pll_nocosim_lpfilt.html
  The loop filter, circuit against model.
  rms error 0.008% of the output's 1.353 V excursion, worst single point 0.019%: PASS (spice2rnm's own verdict)

Not drawn: the ring oscillator and the charge pump on their own.
Their circuit side is a characterisation sweep, not one run with
a matching model run beside it; the loop page shows both at work.

The loop page re-ran the generated loop with a recording and
checked it printed what the demo's run printed. Every other page
is drawn from the demo run's own files.
