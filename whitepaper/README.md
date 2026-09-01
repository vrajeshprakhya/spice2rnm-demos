# Whitepaper

`spice2rnm-demos.tex` — the spice2rnm product whitepaper: three worked
case studies of automatic real-number-model and testbench generation.

## Building

```sh
pdflatex spice2rnm-demos.tex
pdflatex spice2rnm-demos.tex     # again, for the table of contents
```

Standard classes and packages only (`article`, `booktabs`, `listings`,
`xcolor`, `fancyhdr`, `hyperref`), so a stock TeX Live or MiKTeX builds it
with nothing extra to install — or drop the single `.tex` file into
[Overleaf](https://www.overleaf.com) and compile with the default pdfLaTeX
engine.

## Where the numbers come from

Every figure in the paper is machine-produced by the tool itself — none
are typed in by hand. Two places to verify that:

- [`../run_all.sh`](../run_all.sh) runs all three demonstrations end to
  end and prints the headline figures the paper quotes.
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
