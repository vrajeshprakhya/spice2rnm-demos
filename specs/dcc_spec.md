# DCC — Duty Cycle Corrector

## Purpose

Takes a clock whose duty cycle has been degraded by upstream buffering and
restores it toward 50%. Sits between the PLL output buffer and the
serializer clock tree, so both its input and its output are full-swing
CMOS clocks — it is not a linear block and there is no meaningful notion of
gain through it.

The correction point is set by an analog control voltage `vctrl`, which the
duty-cycle detector loop drives. For characterization `vctrl` is held.

## Operating conditions

| Parameter        | Min  | Typ  | Max  | Unit |
|------------------|------|------|------|------|
| Supply (VDD)     | 1.62 | 1.80 | 1.98 | V    |
| Clock frequency  | 50   | 200  | 400  | MHz  |
| Input duty cycle | 35   | 50   | 65   | %    |

Input and output swing rail to rail, 0 V to VDD.

## Requirements

1. **Duty accuracy.** With `vctrl` at its nominal setting, the output duty
   cycle shall track the input duty cycle to within **1 percentage point**
   over the whole stated frequency and input-duty range.

2. **Polarity.** The block is inverting. A 40% input duty produces
   approximately a 60% output duty.

3. **Edge rates.** Output rise and fall times are not matched — the
   pull-down is stronger than the pull-up. This is expected and is
   compensated in the loop, but any behavioural model of this block must
   reproduce the resulting duty offset, because it is the quantity the
   loop is servoing on.

4. **No AC specification.** Small-signal gain and phase are not specified
   and are not meaningful for this block. Do not verify against a
   small-signal frequency response.

## Verification notes

What matters is where the edges land, not the waveform shape. The block
should be driven with clocks at several input duty cycles across the stated
range and the output duty measured; a voltage-domain waveform comparison
will not catch the failure modes that matter here.
