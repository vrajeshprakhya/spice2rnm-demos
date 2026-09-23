# The specifications

Plain-language functional specifications, one per circuit that has one.
They are hand-written, the way a designer or a datasheet would state
them, and the tool reads them with `--spec`: it extracts the facts that
shape verification (operating range, accepted inputs, tolerances, what
the block is for), checks every one against what the circuit was
measured to do, and reports any disagreement as a `SPEC CONFLICT`
finding rather than trusting either side.

| file | case | read by |
|---|---|---|
| `rc_lpf2_spec.md` | the two-pole filter | not used by a demo; published for reference |
| `dcc_spec.md` | the duty-cycle corrector | demo 2 (`--spec`) -- sets the clock range, the input-duty sweep and the 1 pp tolerance its duty environment is judged on |
| `pll_spec.md` | the PLL | demo 4b (`--spec`) -- states the lock requirement, the control window and the supply-noise condition |

Nothing here is generated. These are inputs, kept under version control
so a number in the paper can be traced to the document it was judged
against.
