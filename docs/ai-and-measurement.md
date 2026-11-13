# AI where it helps, physics where it decides

**Whitepaper** §12

spice2rnm asks a language model four kinds of question:

- where one block ends and the next begins,
- what a block is for,
- what a written specification requires,
- what conventions an existing model library follows.

Every one of those is a question about *intent*. Not one of them is a
question about physics.

## The rule

**Intent from the language model, physics from the measurement.**

Every suggestion is checked against the measured circuit before anything uses
it. If it does not match, it is thrown away, the run carries on with the
measured data, and the run says that it did. With no language model reachable
at all, every AI feature switches off cleanly and the pipeline runs on
measurement alone.

## Which of those two happened is recorded

Not just in the log, in the run's result. Each verdict records the metric it
was reached with. So a reader coming back months later can tell a check that
ran as asked from one where the AI feature bowed out and the tool fell back
to measurement. Without that record, you would have to take it on trust that
a passing result used the feature you asked for.

**Asking for a check on the command line does not prove that it ran.** The
PLL case study demonstrates this directly: the same demonstration was run
with the classifier reachable and deliberately unreachable, and the two
transcripts are otherwise alike with an identical command line. With the
classifier unreachable the two clock buffers are driven by the default chirp
and judged on rms voltage, passing at 0.026 and 0.025 against a 0.15 limit.
That is a green result from a measurement that cannot see the property in
question, namely edge timing. The numbers are in
[the case study](cases/04-pll-cosimulation.md#the-passfail-result-names-the-metric-it-came-from).

## Three worked examples of the boundary

### A number that looked like intent and was physics

The clock frequency a buffer should be scored at looked like a judgement
call. It is not. Asked five times about the same inverter with the same
measurements, the classifier proposed 2 MHz, 765 MHz, 300 MHz, 10 GHz and
15 GHz. The lowest is two hundred times below where the buffer runs; the
highest is thirty-seven times above what the buffer's own model can follow.

The measurement returns the same answer every run, and its answers for the
two stages agree to 0.04%, which no classifier run did. So the golden probe
measures the switching rate and the classifier is not asked.

On what it *is* asked for, the classifier has been consistent: buffer, clock
stimulus and duty-cycle metric, on every run of both stages. That is a
judgement it can check against a measurement. What varied was the one number
it had no way to know.

### A number too authoritative to depend on a model being reachable

An operating band decides the range the circuit is measured over in the first
place, so unlike every other fact from a specification it cannot be checked
against a measurement afterwards. A number with that much authority must not
depend on whether a model happened to be reachable, so the
operating-conditions table is parsed as plain text by the part of the
toolchain that always runs, while the rest of the document is read by a
model. The same applies to the one line stating which detector output raises
the control voltage, because it decides how the loop gets *wired*.

[The SV-only PLL page](cases/05-pll-systemverilog-only.md#a-band-is-an-input-not-a-claim)
has both.

### A judgement it made well, and then had checked

Reading a house style is genuinely a judgement call: a library may declare
several nettypes when only one is the current standard, and often the only
thing saying which is a comment. The language model read the deprecation
notice and picked the live convention where a mechanical scan picked the
deprecated one. Then the choice was re-checked against the file that
supposedly showed it, and a claim the file did not support would have been
refused. See
[joining-a-model-library.md](joining-a-model-library.md#reading-a-house-style-takes-judgement).

## What this costs in reproducibility, stated plainly

Every figure in the whitepaper regenerates identically from its run, except
the quoted text where a language model explains what it read. That text does
not, because a model picks different words each time.

What stays stable is everything around it: the bands, the measurements and
the verdicts. All of those were byte-for-byte identical across the published
run, across two earlier runs where the model read the document differently,
and across the run before those, where the reader did not run at all because
no model was reachable. **What a model changed was what was *read*, never what
was measured.**
