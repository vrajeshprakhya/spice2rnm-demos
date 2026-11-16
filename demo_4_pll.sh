#!/usr/bin/env bash
# RENAMED. This demo is now demo_4a_pll_cosim.sh, so that the two PLL cases
# read as a pair: 4a with co-simulation, 4b (demo_4b_pll_nocosim.sh) without.
# Kept so that existing commands and notes still work; it runs the new name
# with the same arguments and environment.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "demo_4_pll.sh has been renamed to demo_4a_pll_cosim.sh; running that." >&2
exec bash "$HERE/demo_4a_pll_cosim.sh" "$@"
