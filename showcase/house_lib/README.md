# A stand-in for *your* model library

Nothing in this directory is generated. It is a small hand-written
real-number-model library — a package declaring a user-defined nettype,
and two models using it — standing in for the library a customer already
has before spice2rnm generates anything for them.

| file | what it is |
|---|---|
| `ng_ams_pkg.sv` | the house package: resolver, `nettype real ng_anet`, shared constants |
| `ng_buffer_rnm.sv` | a hand-written model on the house net |
| `ng_attenuator_rnm.sv` | another |

It exists so [`../lpf2_house/`](../lpf2_house/) can be a real
demonstration rather than a description: that directory holds the same
circuit as [`../lpf2/`](../lpf2/), generated with

```sh
spice2rnm rc_lpf2.cir ... --style-from showcase/house_lib
```

so the generated environment joins *this* library instead of inventing a
net scheme of its own. Diff the two directories to see exactly what
conformance changes — and what it leaves alone.
