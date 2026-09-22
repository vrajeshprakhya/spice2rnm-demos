# PLL — 400 MHz ring-oscillator phase-locked loop

## Purpose

Multiplies a 10 MHz reference up to 400 MHz. The analog half is a charge
pump, a passive loop filter and a seven-stage differential ring; the
digital half is a phase-frequency detector and a divide-by-40 counter,
both of which are RTL and appear nowhere in the netlist.

The two halves are delivered separately and are **not wired together**.
There is no co-simulation, no bridge and no testbench that spans them.
What is wanted is a model of the analog half that the RTL can be closed
around in a SystemVerilog simulator.

## Operating conditions

| Parameter          | Min  | Typ  | Max  | Unit |
|--------------------|------|------|------|------|
| Supply (VDD)       | 3.13 | 3.30 | 3.47 | V    |
| Reference          |      | 10   |      | MHz  |
| Output             |      | 400  |      | MHz  |
| Divide ratio       |      | 40   |      |      |
| Control voltage    | 1.75 | 1.85 | 1.95 | V    |

The supply is not quiet: 20 mV rms of wideband noise is specified on it,
and the ring is about as sensitive to its rail as it is to its own
control input.

The control voltage range is the one that matters. The ring is
characterizable from 0.5 V to 2.8 V, but in a locked loop the control
sits in a 200 mV window around 1.85 V, and a verdict taken over the whole
range is failing the block over a bias the design never reaches.

## Blocks

1. **`ro_vco`** — seven-stage differential ring. Oscillates with its
   inputs held at DC, so its behaviour is a **frequency**, not a gain.
   Its tuning slope is **negative**: raising the control voltage lowers
   the frequency.

2. **`cpump`** — a complementary pair driving one node from two
   independently controlled gates, `pdn` and `pupb`. It is a switched
   current driver, not a gain stage. `pdn` and `pupb` are the only two
   nodes the digital side drives.

3. **`lpfilt`** — resistors and capacitors only. Its state space is exact
   from the topology and nothing about it needs fitting.

## Requirements

1. **Lock.** Closed around the supplied RTL at a 10 MHz reference, the
   loop shall hold 400 MHz to within **2%**, measured after settling.

2. **The control voltage is the number to read.** It is where the loop
   stores its state, so a model that settles anywhere else disagrees
   there first.

3. **Supply sensitivity shall survive into the model.** A model whose
   oscillator has no supply input cannot show a droop at all, and the
   rail on this design is specified noisy.

4. **No small-signal specification.** None of the three blocks has a
   meaningful transfer function. Do not verify any of them against a
   frequency response.

## Verification notes

Acquisition from a cold start is **not** in scope: it is hours of
transistor SPICE, which is why the deck states an initial condition on
the control node. What is in scope is holding lock from that condition,
at one operating point, one corner and one reference rate.
