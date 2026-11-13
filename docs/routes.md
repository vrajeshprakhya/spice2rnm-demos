# What the routes measure

**Whitepaper** Appendix A

A route is the method the tool picks for measuring a block. The case studies
name each block's route and say why that block needs it. This page says what
the routes actually measure, using the reference PLL's own numbers rather
than a made-up example.

You do not need this page to read the results. It is here if you want to
check them.

## Why an oscillator is compared as a rate

Most blocks are checked by laying two output waveforms on top of each other
and subtracting. That is the first row of the table in
[equivalence.md](equivalence.md#each-block-is-judged-on-its-own-job). An
oscillator, the fourth row, cannot be checked that way at all, and the reason
is the whole case for giving it a route of its own.

Picture a perfect model, running at exactly the frequency the transistors run
at. The two start in step. Nothing holds them there. Let their frequencies
differ by one part in 10⁵ and inside a millisecond they have slid a full cycle
apart. From then on the model sits at one supply rail whenever the circuit
sits at the other. Subtract the waveforms and you get full-swing error
everywhere. The perfect model scores as completely wrong.

This is not a thought experiment. A milder version of it appears in the PLL
case study. The two clock buffers report a worst-instant error of 99.9% of
full swing, because an edge lands slightly late. In a buffer that bad instant
lasts a moment per cycle. In an oscillator it would be the permanent state of
affairs.

So the oscillator route subtracts nothing. It compares rates instead. Set the
control voltage. Run the transistors in SPICE and count cycles. Run the model
at the same control voltage and count its cycles. Compare the two
frequencies:

| | |
|---|---|
| set `cont` to | 1.9000 V |
| SPICE: count cycles, divide | *f*<sub>spice</sub> |
| model: same control, count | *f*<sub>model</sub> |
| score | &#124;*f*<sub>model</sub> − *f*<sub>spice</sub>&#124; / *f*<sub>spice</sub> = 0.024% |
| pass/fail limit | 2% |

Phase is ignored on purpose. The model never claims to reproduce it: what it
puts out is an ideal square wave. The real ring's finite edge rates were
already accounted for when its frequency was measured by FFT.

## The tuning curve

For an oscillator the tuning curve is not a description of the model. It *is*
the model. The route measures a table with one row per control voltage. Each
row is its own transient run of the transistors in SPICE, with the control
voltage pinned and the resulting oscillation timed:

| `cont` (V) | frequency (MHz) |
|---:|---:|
| 0.495 | 804.47 |
| ⋮ | ⋮ |
| 1.750 | 438.73 |
| 1.850 | 399.86 |
| ⋮ | ⋮ |
| 2.805 | 16.74 |

The model looks its frequency up in this table and interpolates between rows.
That is why its checks come in three kinds:

- **At the table's own 15 rows.** The model is exact here by construction. The
  agreement (0.001%) only shows that the table was copied across correctly.
- **At 5 control voltages *held back* from the table.** Here the model has to
  interpolate, and it is compared against fresh SPICE runs. This number,
  0.024%, is the only one of the three that says anything about accuracy.
- **At 9 voltages far outside where the closed loop goes.** Out there the
  error reaches 4.987%. It is reported for information, with no pass/fail
  limit, because the loop never visits.

[The SV-only run](cases/05-pll-systemverilog-only.md) reads the same table
backwards. Ask it for 400 MHz and it answers 1.8496 V. The assembled loop is
then required to settle at that control voltage, which catches a loop that
reaches the right frequency by the wrong route.

## Control states

A control state is one combination of the digital inputs driving a block. The
charge pump has two of them, `pdn` and `pupb`, and they are driven
*independently*. So it has four states rather than one continuous knob. Each
state gets its own measured table of current against output voltage, *I(V)*:
12 points from 0 to 3.3 V, with 11 more held back for checking.

| state | (`pdn`,`pupb`) | *i* at 1.80 V | at 3.3 V | what it does |
|---|---|---:|---:|---|
| 00 | (0,0) | +7.239 mA | ≈ 0 | sources: charges the filter |
| 01 | (0,1) | −1.9 nA | −4.0 nA | high-Z: off |
| 10 | (1,0) | +2.798 mA | −5.078 mA | both on, fighting |
| 11 | (1,1) | −4.441 mA | −5.078 mA | sinks: discharges it |

**Why one table per state, not one fitted curve.** The gates are digital.
Each one is either on or off, so there is no continuous knob to fit a curve
against. What there is instead is a small, fixed set of modes. Inside a mode,
the current depends only on the output voltage, because how much current you
can push into a node depends on the voltage already sitting there. That is
what *I(V)* means here, and why there are four tables.

It is also why the default route cannot model this pump. The pipeline works
that out from the shape of the circuit, not from the block's name. An inverter
ties its two gates together, so one input drives both and there is a single
thing to fit against. In the pump the two gates are separate signals. That
makes states 01 and 10 reachable, and an inverter has neither. State 01 is the
idle one, drawing nanoamps. State 10 has both transistors conducting at once.

**These four rows do work in two other places.** First,
[the SV-only loop](cases/05-pll-systemverilog-only.md#gate-polarity-comes-from-measurement)
uses them to work out each gate's active level. It reads them at 1.849 V,
where the loop settles, rather than at a table row. With `pupb` idle, `pdn` at
1 reaches state 11 and sinks 4.47 mA, so `pdn` is active high. With `pdn`
idle, `pupb` at 0 reaches 00 and sources 7.103 mA, so `pupb` is active low.
Second, the equivalence verdict names the state its worst error happened in:
0.5487% against a 2% limit, at state 00. An average over the four modes would
hide which mode is the weakest.

## The state space

A filter can be written down exactly, so its route needs to measure nothing
at all. The standard way to write a linear dynamic system is a state space: a
few variables whose *rates of change* depend on where they are now and on the
input, ẋ = Ax + Bu, y = Mx + Nu. In an RC network the state variables are
simply the capacitor voltages. Here is the netlist:

```spice
.subckt lpfilt dra vout
R1 dra  int1 300        C1 c1   0  10n
R2 int1 c1   200        C2 int1 0   5n
R3 int1 vout 50         C3 vout 0  0.5n
.ends
```

Three capacitors, so three states: the voltages on `c1`, `int1` and `vout`.
The input is the current the charge pump pushes into `dra`. The output is
`vout`. When the case study calls this route "exact and needs no fitting", it
means every coefficient in the generated model is worked out from numbers
written on those six lines:

| generated coefficient | is | which is |
|---|---|---|
| 500,000 | 1/(R₂C₁) = 1/(200 × 10 n) | the `c1` pole |
| 40,000,000 | 1/(R₃C₃) = 1/(50 × 0.5 n) | the `vout` pole |
| 1,000,000 | 1/(R₂C₂) = 1/(200 × 5 n) | `c1` into `int1` |
| 4,000,000 | 1/(R₃C₂) = 1/(50 × 5 n) | `vout` into `int1` |
| 200,000,000 | 1/C₂ = 1/5 n | the injected current |

Not one of these came from a simulation. Compare the inverter in the same
netlist: there the tool ran SPICE 33 times, fitted a curve, and reports an rms
fit error. Here there is nothing to fit, so there is nothing to get wrong.
Kirchhoff's laws and the netlist settle the answer between them. The
comparison can still catch a code-generation bug, meaning a generated file
that disagrees with the matrices it was built from. That is what its 0.019%
measures.

Two details of the generated file come out of the same reasoning. First, `dra`
is *not* a state, because it has no capacitance. Its voltage is set at every
instant by the resistors and the injected current, so it is solved
algebraically at each time step, together with the pump that drives it.
Second, the filter has no DC path to ground. A steady injected current
therefore ramps the output up forever and never settles. That is exactly what
a charge pump driving a capacitive filter does, and it is why the filter is
modelled as a state space rather than as a DC gain.

The generated file is
[`../showcase/pll_cosim/lpfilt.sv`](../showcase/pll_cosim/lpfilt.sv).
