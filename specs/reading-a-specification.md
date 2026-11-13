# How the tool reads these documents

**Whitepaper** §10 · The documents themselves are described in
[README.md](README.md)

A netlist says what a circuit *is*. It says nothing about what the circuit is
*for*, what rate it has to run at, or how much error you are willing to
accept.

You can hand the tool those facts as a plain-language document: a datasheet
excerpt, a requirements page, one of the files in this directory. The tool
reads out the facts that shape the verification:

| From the specification | Used for |
|---|---|
| operating clock range | where the environment drives the block |
| accepted input duty range | the stimulus sweep |
| duty accuracy requirement | the pass/fail tolerance |
| block function | which environment is generated |

## A worked example

[Case study 2](../docs/cases/02-duty-cycle-corrector.md) is run this way. It
reads [`dcc_spec.md`](dcc_spec.md). Its duty-cycle environment drives 35% to
65% input duty at the clock rates the document names, and judges the result
against the document's own 1.0 pp requirement. Result: 14 checks, 0 failed,
worst 0.428 pp. **Pass.**

[Case study 4b](../docs/cases/05-pll-systemverilog-only.md) reads
[`pll_spec.md`](pll_spec.md), which does three further jobs: it states the
lock requirement, it supplies the two operating bands no netlist can
(the control window and the supply range), and it states in one line which
detector output raises the control voltage, which is how the loop gets wired.

## The specification is cross-checked, never trusted

Every fact taken from it is compared with what the circuit was measured to
do, **and the measurement wins.** When the two disagree, the tool reports the
disagreement:

```
SPEC CONFLICT: the spec says this block operates up to 4e+08 Hz, but
the fitted model is only valid below 1.195e+08 Hz -- 3.3x lower.
```

That is a gap in coverage: the requirement asks for more than the
measurements cover. It is caught when the model is generated, not months
later at silicon correlation. Reviewing the model by hand cannot find it,
because no single document holds both the requirement and the measurement.

## One kind of fact is treated differently, on purpose

Most of what the tool takes from a document is a claim about what the part is
*for*. Those choose the stimulus and the verdict, and the measurement can
contradict them, so they are read by a language model and then checked.

An **operating band** is not like that. It decides the range the circuit is
measured over in the first place, so there is no later measurement to check
it against. A number with that much authority must not depend on whether a
language model happened to be reachable. So the operating-conditions table is
parsed as plain text by the part of the toolchain that always runs, with no
model involved. The same goes for the one line stating the loop sense, because
it decides how the loop gets *wired*.

The run labels every band with where it came from, in those words: `DERIVED`
for a fact read off the netlist, `DECLARED` for one taken from the
specification's table, and neither of those is dressed up as measured. The
full set for the PLL is on
[its page](../docs/cases/05-pll-systemverilog-only.md#problem-one-nothing-measures-the-operating-band).

## An environment is exactly as strict as the document

No stricter. A requirement is what the circuit is held to, and an environment
that quietly applied a tighter limit would report failures the design does not
have.

That cuts both ways, and the tool measures the cost rather than leaving you to
guess. The duty-cycle corrector's specification allows 1.0 pp; the tool's own
default for that environment would have been 0.5 pp. The fault sweep in
[trusting-a-testbench.md](../docs/trusting-a-testbench.md#every-environment-is-proven-able-to-fail)
shows what the looser limit lets through: a tenfold slow-down of the block
shifts the duty by 0.87 pp and passes. You can then decide whether 1.0 pp is
the requirement you meant to write.

## What the tool will say it cannot do

A requirement it cannot yet meet is flagged in the output rather than quietly
dropped. The PLL specification names 20 mV rms of supply noise as a condition
the part has to work under. The reader placed that correctly, in the stimulus
rather than the model, and then reported that the generated environment does
not drive it:

```
NOTE: the supply-noise condition is not driven by the generated
  environment yet; the composition carries only the noise the
  netlist itself declares
```

That is the behaviour worth having from a language model in a verification
flow: not a guess at a fix, but a gap it can name.
