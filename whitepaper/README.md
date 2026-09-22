# Whitepaper

`spice2rnm-demos.tex` — the whitepaper for spice2rnm, Veylon Systems'
automatic real-number-model and testbench generator: four worked case
studies, the last of them run twice --- once against a co-simulation,
once with none at all.

**Read it compiled: [`spice2rnm-demos.pdf`](spice2rnm-demos.pdf)** (23
pages). The PDF is regenerated from the `.tex` whenever it changes; if
the two ever disagree, the `.tex` is the source of truth.

## Building

```sh
pdflatex spice2rnm-demos.tex
pdflatex spice2rnm-demos.tex     # again, for the table of contents
```

Standard classes and packages only (`article`, `booktabs`, `listings`,
`xcolor`, `fancyhdr`, `hyperref`, `draftwatermark`, `pgfplots`), so a
stock TeX Live or MiKTeX builds it
with nothing extra to install — or drop the single `.tex` file into
[Overleaf](https://www.overleaf.com) and compile with the default pdfLaTeX
engine.

## Where the numbers come from

Every figure in the paper is machine-produced by the tool itself — none
are typed in by hand. Two places to verify that:

- [`../run_all.sh`](../run_all.sh) runs the four demonstrations end to
  end and prints the headline figures the paper quotes.
- [`../demo_4b_pll_nocosim.sh`](../demo_4b_pll_nocosim.sh) is the source
  of the no-co-simulation figures in case study 4. It is **not** in
  `run_all.sh` --- it costs about as long again as demo 4 --- so it is
  run on its own.
- [`../showcase/`](../showcase/) holds the generated artifacts themselves
  — models, verification environments, and evidence files — with
  [`STAMP`](../showcase/STAMP) recording when they were generated, by
  which tool version, and with what results.

If a number in the paper and a number from a fresh run ever disagree, the
paper is the stale one: the figures are regenerated, never edited.

The fault-injection results ("Why a green testbench is worth believing")
are produced by the product's environment-validation tooling, which
injects faults into a generated model and confirms the generated checks
detect them. They are re-measured against the shipped model whenever the
model generation changes.
