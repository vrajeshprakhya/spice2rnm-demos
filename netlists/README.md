# The inputs

The SPICE netlists the five case studies run, exactly as they run them.
Every artifact under `../showcase/` was produced from one of these files;
the demos read them from here, so what is published is what ran.

| file | case | what it is |
|---|---|---|
| `rc_lpf2.cir` | demo 1 | a two-pole passive RC low-pass filter, PDK-free, corner ~10 MHz |
| `dcc.cir` | demo 2 | a comparator-based duty-cycle corrector |
| `pi_therm.cir` | demo 3 | a thermometer-coded phase interpolator, 8 codes |
| `pll_analog.cir` | demos 4 and 4b | the analog half of a 400 MHz ring-oscillator PLL: charge pump, loop filter, seven-stage differential ring with its output buffers |

**Provenance of the PLL deck.** It is `examples/pll/pll_analog.cir` from
[ams-cosim](https://github.com/vrajeshprakhya/ams-cosim) with exactly
one change: the supply card `vdd dd 0 dc {vcc}` carries
`trnoise(0.02 1e-10 0 0)`, 20 mV rms redrawn every 100 ps -- the
operating condition the specification states, and the reason the PLL
case studies run on a noisy rail. Both demos assert that card is present
before running anything. The RTL the loop closes around (`pfd.sv`,
`divn.sv`) is the example's own and is published, unchanged, under
`../showcase/pll_nocosim/rtl/`.

Nothing here is generated. These files are hand-written circuits, kept
under version control so that a number in the paper can always be traced
to the deck that produced it.
