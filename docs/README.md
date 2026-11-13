# Documentation

The whitepaper, split into pages you can read one at a time.

[`../whitepaper/spice2rnm-demos.pdf`](../whitepaper/spice2rnm-demos.pdf) is
the same material as one 35-page document. These pages exist because most
people arrive with one question, not thirty-five pages' worth, and because a
page sitting next to the files it describes is easier to find than a section
number.

## Start here

| If you want to know | Read |
|---|---|
| what problem this solves, and what one command gives you | [the-problem.md](the-problem.md) |
| what a term in these pages means | [glossary.md](glossary.md) |
| whether it works, on real circuits | [cases/](cases/) |
| how a model is proven to match the circuit | [equivalence.md](equivalence.md) |
| why a passing generated testbench is worth believing | [trusting-a-testbench.md](trusting-a-testbench.md) |
| what the tool will and will not do | [scope.md](scope.md) |

## Every page

**Getting oriented**

- [the-problem.md](the-problem.md) : why hand-written models drift, and what
  comes out of a single `spice2rnm` command.
- [glossary.md](glossary.md) : real-number model, route, golden value, bar,
  co-simulation, and the rest, each in a sentence or two.

**The case studies**

- [cases/](cases/) : five circuits, one command each, with the results and the
  reason each one is in the paper.

**How the claims are made**

- [equivalence.md](equivalence.md) : the circuit and the model get the same
  input, and their outputs are compared in the way that matters for that
  block. Includes what keeps a figure from flattering itself.
- [routes.md](routes.md) : what a tuning curve, a control state and a state
  space actually are, using the reference PLL's own numbers.
- [jitter.md](jitter.md) : the one error a score at a fixed operating point
  cannot see, and the two different jitter jobs the tool does.
- [trusting-a-testbench.md](trusting-a-testbench.md) : the same tool writes
  the model and the test. Three rules stop that being circular, and one of
  them is a measured fault sweep.
- [ai-and-measurement.md](ai-and-measurement.md) : intent from the language
  model, physics from the measurement, and what is recorded so you can tell
  which happened.

**Fitting it into your flow**

- [joining-a-model-library.md](joining-a-model-library.md) : generating
  against the nettype, package and port discipline your library already uses.
- [../specs/reading-a-specification.md](../specs/reading-a-specification.md) :
  what the tool takes from a plain-language specification, and why the
  measurement always wins.
- [scope.md](scope.md) : what goes in, what comes out, what you need
  installed, which blocks are covered.

## Where the numbers come from

Every figure in these pages is quoted from the whitepaper, and every figure
in the whitepaper was produced by the shipped tool from the circuits in
[`../netlists/`](../netlists/), most recently on 2026-09-22. None are typed
in by hand.

So if a number here and a number from a fresh run ever disagree, these pages
are the stale ones. The order of authority is: the run, then
[`../whitepaper/spice2rnm-demos.tex`](../whitepaper/spice2rnm-demos.tex),
then the PDF, then these pages. Each page links to the generated evidence it
is describing, so you can go and check.

One place these pages deliberately hold less than the PDF: the PDF carries
plotted waveforms (the filter tracking a chirp, the duty corrector's falling
edge, the interpolator's edge per code, the PLL's control voltage). Those are
regenerated from the run directories by
[`../whitepaper/make_traces.py`](../whitepaper/make_traces.py) and have no
markdown equivalent, so the case pages point at the PDF page for the picture
and at the CSV the picture was drawn from.
