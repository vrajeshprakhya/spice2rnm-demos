# Case study 3: phase interpolator

**Netlist** [`../../netlists/pi_therm.cir`](../../netlists/pi_therm.cir) ·
**Run it** `./demo_3_pi.sh` ·
**Generated output** [`../../showcase/pi/`](../../showcase/pi/) ·
**Whitepaper** §5

A phase interpolator does not touch a signal's amplitude. It moves the signal
in *time*: each control code nudges the clock edge a little further along. So
there is no frequency response worth fitting, and comparing voltages only
measures noise. Conventional flows have nothing to offer this block.

spice2rnm recognises what the block does and changes its approach. It
measures how far the edge moves at each control code, and builds a delay-line
model out of those measurements. Then it generates a *phase* testbench: one
check per control code, against the value measured in SPICE. The testbench
has no DC or AC section, because neither of those tells you where an edge
lands.

## Results

| | |
|---|---|
| Codes measured | 9 of 9 |
| Total edge movement, code 0 to 8 | −500.1 ps, monotonic |
| Mean step (1 LSB) | −62.51 ps |
| Worst step error (DNL) | −100.5 ps (−1.61 LSB) |
| UVM-MS phase section | 9 checks, 0 failed |
| worst | 3.26 ps of a 6.25 ps tolerance |

Two terms there need a word. **One LSB** (least significant bit) is one step
of the control code. The nine codes span 500.1 ps in eight steps, so the
average step is 62.51 ps, and that average is the natural unit for everything
else here. **DNL** (differential non-linearity) is how far an individual step
sits from that average.

## The steps in this circuit are very uneven, and that is the point

Subtract each measured edge position from the next and you get eight steps of
−17, −30, −48, −163, −153, −48, −28 and −12 ps. Every one of them should be
−62.5. The worst is the fourth: it moves 163 ps for a single code change,
100.5 ps more than it should. That is the −1.61 LSB in the table.

This matters in a real system. A phase interpolator usually sits in a control
loop that walks a sampling clock one code at a time to keep it centred in a
data eye. That loop assumes each code change is worth about one LSB. Here one
code change moves the edge 12 ps and another moves it 163 ps, so the loop's
gain varies by more than 13× depending on where it starts.

The tolerance per code is a tenth of an LSB, the finest step the model can
resolve. Tight enough to catch a real error, loose enough never to fail on
rounding.

**The uneven steps are the circuit's own imperfection, reported exactly as
measured.** The model's job is to reproduce them, and it does. A model with
evenly spaced steps would look tidier, but it would hide a real defect from
anyone verifying against it.

## What the environment looks like

[`pi_therm_ms_pkg.sv`](../../showcase/pi/pi_therm_ms_pkg.sv) holds one
measured phase golden per thermometer code. There is no DC section and no AC
section, and no bridge pair either, because the environment measures edges
directly.

[`pi_therm_rnm.sv`](../../showcase/pi/pi_therm_rnm.sv) is worth opening for
two other reasons. It is the repository's example of a **digital code port
crossing an analog boundary**: `input int code` stays `int` beside the wreal
ports. And it asserts its own validity range as `a_code_range` rather than an
amplitude domain, because a delay line has no amplitude domain to assert.

## The picture

The whitepaper plots edge position at each of the nine control codes: the
transistors in SPICE in black against the generated model in red. There is no
waveform to compare. What this block does is place a clock edge, so edge
position is what gets plotted.

The nine rows behind that plot are in
`equivalence/phase_compare.csv`: the measured delay, the model's delay, and
the error, one row per code. It is small enough to read, so it is committed
rather than listed in `MANIFEST.txt`.

## Published verdict

The equivalence check's published verdict is worst 1.832 ps at code 2,
against a 6.251 ps tolerance. The 3.26 ps in the table above is the worst
check reported by the UVM-MS scoreboard, which is a separate run of a
separate thing: the equivalence verdict compares the per-code measurement,
while the environment runs its own sequences. Both figures are published, in
[`equivalence/verdict.txt`](../../showcase/pi/) and in `result.json` beside
it.
