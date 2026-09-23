# RC-LPF2 — anti-alias filter

Two-pole passive RC low-pass ahead of the ADC sampler.

## Operating conditions

| Parameter        | Min | Typ | Max | Unit |
|------------------|-----|-----|-----|------|
| Supply (VDD)     | 1.62| 1.80| 1.98| V    |
| Input voltage    | 0.2 | 0.9 | 1.6 | V    |

The input is driven by the preceding buffer, whose output never leaves
0.2 V to 1.6 V. Behaviour outside that window is not specified and the
block is not characterized for it in silicon.

## Requirements

1. Passband ripple below 0.5 dB to 1 MHz.
2. Attenuation at least 20 dB at 50 MHz.
