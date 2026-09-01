# Whitepaper

`spice2rnm-demos.tex` — the three demos written up as marketing material.

## Building

```sh
pdflatex spice2rnm-demos.tex
pdflatex spice2rnm-demos.tex     # again, for the table of contents
```

Standard classes and packages only (`article`, `booktabs`, `listings`,
`xcolor`, `fancyhdr`, `hyperref`, ...), so a stock TeX Live or MiKTeX is
enough and there are no local `.sty` files to install.

**This has not been compiled.** No TeX toolchain was available on the
machine it was written on. It was checked structurally instead — balanced
environments, balanced braces, every custom macro defined before use, and
every `tabular` row's cell count matching its column spec — but the first
person with `pdflatex` should expect to fix spacing rather than errors.

## Keeping the numbers true

Every figure in the paper is machine-produced. To re-derive them:

```sh
cd ..           && ./run_all.sh              # the demo figures
cd ../spice2rnm && python3 tests/run_tests.py --suite unit
                   python3 tests/run_tests.py --suite e2e
```

The paper's closing note states the date those were last run and the suite
results at that time. If a number in the paper and a number from `run_all.sh`
disagree, the paper is the stale one — update it rather than the other way
round.

The fault-injection table ("Why a green testbench is worth believing") comes from
`spice2rnm/work/fault_inject_duty.sh`, which takes several minutes and is
not part of either suite.
