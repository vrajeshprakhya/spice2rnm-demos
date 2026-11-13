# Joining an existing model library

**Whitepaper** §11 · **Generated output**
[`../showcase/lpf2_house/`](../showcase/lpf2_house/) against
[`../showcase/house_lib/`](../showcase/house_lib/)

A team that already has real-number models also has house rules: which
user-defined nettype carries analog values, which package declares that
nettype, and what port discipline the models use.

Generated files that import a nettype the tool made up do not join that
library. They sit beside it, the two net schemes cannot be wired together,
and the customer pays to bridge them.

## What `--style-from` changes

Point it at the library and the output follows its conventions:

- the environment's analog nets use the library's nettype,
- its files import the library's package,
- the tool generates no types package of its own,
- the generated run script compiles the library's package file,
- and if the library's models use `wreal` ports, the generated model gets
  wreal ports too, without being asked.

One thing is deliberately not copied: the library's timescale. It is reported
instead. Generated delays are computed femtosecond values, and timescale
applies per compilation unit, so the two timescale directives work together
unchanged.

## Reading a house style takes judgement

So the tool reads it and then checks itself. A library may declare several
nettypes when only one of them is the current standard, and often the only
thing saying which is a comment. We measured this on a library that declares
two, where the deprecated one happens to sort first alphabetically:

| | |
|---|---|
| mechanical scan | picks the deprecated nettype, and warns |
| language-model reading | picks the current one, quoting the deprecation notice |
| verification | re-checks the choice against the named file |

Here is why the language model said what it said, word for word from that
run: *"line 15 marks `aaa_legacy_wire` deprecated ("kept only so ancient
testbenches still compile. Do NOT use in new code"), ... both models declare
all analog ports as `acme_ewire`, confirming this is the live convention."*

None of that is taken on trust. The nettype, the package and the file it
names are all checked against the file before anything uses them. If the file
does not back the claim, the mechanical scan's answer stands and the run says
that it fell back. And where the tool has a *measurement* of its own, here a
count of which port discipline the library's models actually use, the count
wins outright. Anything that disagrees with it is recorded, not adopted.

That division is the general rule set out in
[ai-and-measurement.md](ai-and-measurement.md).

## The result, published twice over

The showcase carries the same filter twice. `lpf2/` was generated normally.
`lpf2_house/` was generated against `house_lib/`, a small hand-written
library standing in for a customer's own. Diff the two directories and the
whole effect shows up:

```sh
cd showcase && diff -r lpf2 lpf2_house
```

| | `lpf2/` | `lpf2_house/` |
|---|---|---|
| types package | generated | **not generated** |
| nets | `rc_lpf2_wire` | `ng_anet` |
| imports | the generated package | `ng_ams_pkg` |
| run script | compiles the generated package | compiles the house package |
| model ports | plain `real` | `ng_anet`, and the environment instantiates it |
| the model | byte-identical | byte-identical |
| the scoreboard | byte-identical | byte-identical |

**Following the house style changes the boundary of the model and nothing
else.** The published environment runs where it sits, against the library
next to it: 49 DC and 15 AC checks, 0 failed, the same result as the default
environment.

## Why the second column's last row matters

Look at what the environment instantiates. When the model ships inside a port
wrapper, the generated testbench drives that wrapper, not the core inside it,
and the wrapper's file joins the compile list. So the evidence covers what you
actually ship, not just one piece of it.

In separate measurements, a library whose nettype resolves multiple drivers by
averaging instead of summing also conforms, and passes the same way. A library
using `wreal` ports gets wreal ports on the model instead.

Without `--style-from`, or pointed at a directory with nothing recognisable in
it, nothing changes, and the run says so.

## The three boundaries, and where to find one of each

| Looking for | Open |
|---|---|
| a model with **wreal** ports | [`../showcase/lpf2/rc_lpf2_rnm.sv`](../showcase/lpf2/rc_lpf2_rnm.sv) |
| a model with plain **`real`** ports | [`../showcase/lpf2_house/rc_lpf2_rnm.sv`](../showcase/lpf2_house/rc_lpf2_rnm.sv), and [`../showcase/pll_cosim/ro_vco_rnm.sv`](../showcase/pll_cosim/ro_vco_rnm.sv) whose output is a `logic` clock rather than an analog node |
| a model with **UDN** ports, on a library's own nettype | [`../showcase/lpf2_house/rc_lpf2_rnm_ng_anet.sv`](../showcase/lpf2_house/rc_lpf2_rnm_ng_anet.sv) |
| a **UDN declaration** the tool generated | [`../showcase/lpf2/rc_lpf2_ms_types_pkg.sv`](../showcase/lpf2/rc_lpf2_ms_types_pkg.sv) |
| a **UDN declaration** a customer already had | [`../showcase/house_lib/ng_ams_pkg.sv`](../showcase/house_lib/ng_ams_pkg.sv) |
| `interconnect` ports (IEEE 1800-2017 §6.6.8) | [`../showcase/lpf2/rc_lpf2_dms.sv`](../showcase/lpf2/rc_lpf2_dms.sv) |
| what a **conformed** run script compiles | [`../showcase/lpf2_house/run_rc_lpf2_ms.sh`](../showcase/lpf2_house/run_rc_lpf2_ms.sh) |

Every case also carries a `*_wreal.sv` wrapper: the same core model behind
`wreal` ports, for flows standardised on wreal nets. Ten lines of discipline
conversion around an untouched core, because adopting the model should never
mean adopting a net discipline.

Which port type is the default, and what each one costs, is in
[the-problem.md](the-problem.md#a-systemverilog-real-number-model).
