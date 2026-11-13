# Scope and requirements

**Whitepaper** §13

## What goes in

SPICE netlists, flat or with subcircuits. Optionally, a plain-language
specification, and an existing RNM library whose conventions the generated
models should copy.

## What comes out

SystemVerilog real-number models, with whichever port type you ask for:
`wreal` by default, plain `real` for a flow that has no wreal support, or
your own library's nettype (see
[joining-a-model-library.md](joining-a-model-library.md)).

Also UVM-MS 1.0 environments, and equivalence reports with the waveforms
kept.

## What you need installed

A SPICE simulator to do the measuring, and a digital simulator that can run
real-number models, with UVM support for the generated environments.

The models and environments are standard SystemVerilog, tied to no vendor, so
either simulator can be the one you already use. Everything published here was
produced with open-source tools: **ngspice** did the measuring and the
reference transient runs, and **xezim**, an open-source IEEE 1800 simulator
that runs the Accellera UVM library, ran both the SV–SPICE equivalence
co-simulation and the generated UVM-MS environments. No commercial licence
was used anywhere.

The PLL co-simulation case needs more than the others: being the analog half
of a co-simulation, it needs the other half, which means the RTL, the DPI
bridge, and a *shared* libngspice. That is a different ngspice build from the
standalone binary the first three cases use. The demo script looks for each
piece before it does any work, and stops naming the missing one rather than
failing twelve minutes into a run.

## Which blocks

Single-input single-output blocks, and blocks built out of those, including
current-mode blocks that share a node.

Stacking blocks into a hierarchy buys you structure and costs you a little
accuracy. The equivalence report prints the stacked figure separately from the
per-block figures, so you can see what the stacking cost.

Some blocks are refused, with the reason written out, and that is the intended
behaviour rather than a gap. In the PLL, the charge pump's result is a current
for each control state and the filter's is a voltage produced by an injected
current; every generated environment scores a voltage against a stimulus, so
neither fits. `gaincell` gets no model at all, because it has two inputs and
two outputs, so no method that fits one input to one output can measure it.

## Jitter

Two different jobs, both done, and only one of them with a pass/fail limit.
[jitter.md](jitter.md) is the full treatment. In short:

- **Jitter transfer** is what the model does with a disturbance you hand it.
  This gets a verdict. The disturbance is injected into the transistors in
  SPICE, the very same disturbance is replayed into the model, and the period
  jitter of the two is compared, on the control input and on the supply. Six
  points over a tenfold range, worst ratio 0.940 against a 0.25 tolerance. The
  pipeline ran it unasked, because the netlist declares noise on a net the
  ring oscillator is wired to.
- **The oscillator's own noise** is measured through its impulse sensitivity
  function Γ(φ) and carried as a model parameter, shipped set to zero. It is
  worked out from the measured ISF rather than compared against a SPICE
  transient, because ngspice does not simulate device noise in a transient
  run.
- **Synchronous jitter in driven blocks** is a figure you supply. It is not
  measured, and it cannot be: a SPICE transient of a netlist that declares no
  noise holds no delay variation to measure. The generated file says so.
- **Edge jitter** is measured wherever the transistors have clock edges, and
  reported for information with no limit, because there is no agreed
  threshold for it.

## Two limits stated plainly

**An SV-only result is not evidence about the circuit.** A loop that settles
at a plausible but wrong point still settles. Only a run with transistors in
it can catch that. See
[what the SV-only run does not carry](cases/05-pll-systemverilog-only.md#what-this-result-does-not-carry).

**No intrinsic device noise in the model.** The model carries its measured
own-noise figure as a parameter shipped at zero. This gap is one published
practice shares, and [jitter.md](jitter.md#where-this-sits-against-published-practice)
cites the comparison.
