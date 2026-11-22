#!/usr/bin/env bash
# Builds the GitHub Pages site: every zoomable waveform page under
# showcase/<case>/waveforms/, plus an index linking them. Nothing else in
# the repository is served. Run by .github/workflows/pages.yml; run it by
# hand to look at the site before it goes out:
#
#   showcase/build_pages.sh /tmp/site && python3 -m http.server -d /tmp/site
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-_site}
rm -rf "$OUT"
mkdir -p "$OUT"

rows=""
n=0
for f in "$HERE"/*/waveforms/*.html; do
  [ -e "$f" ] || continue
  case_name=$(basename "$(dirname "$(dirname "$f")")")
  mkdir -p "$OUT/$case_name"
  cp "$f" "$OUT/$case_name/"
  # the page's own <title> is already HTML-escaped
  title=$(sed -n 's:.*<title>\(.*\)</title>.*:\1:p' "$f" | head -1)
  kb=$(( $(stat -c %s "$f") / 1024 ))
  rows="$rows      <li><a href=\"$case_name/$(basename "$f")\">$title</a>
        <span>$case_name, $kb KB</span></li>
"
  n=$((n + 1))
done
[ "$n" -ge 1 ] || { echo "build_pages.sh: no waveform pages under $HERE/*/waveforms/" >&2; exit 1; }

cat > "$OUT/index.html" <<EOF
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>spice2rnm demo waveforms</title>
<style>
:root { --bg: #ffffff; --ink: #1f2328; --muted: #59636e; --line: #d8dee4; --link: #0969da; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0d1117; --ink: #e6edf3; --muted: #9198a1; --line: #30363d; --link: #4493f8; }
}
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 32px 16px 48px; }
h1 { font-size: 24px; margin: 0 0 8px; }
p { color: var(--muted); }
ul { list-style: none; padding: 0; margin: 24px 0; }
li { padding: 12px 0; border-top: 1px solid var(--line); }
li:last-child { border-bottom: 1px solid var(--line); }
a { color: var(--link); text-decoration: none; font-weight: 600; }
a:hover { text-decoration: underline; }
li span { display: block; font-size: 13px; color: var(--muted); }
</style>
</head>
<body>
<main>
<h1>spice2rnm demo waveforms</h1>
<p>Each page overlays a circuit, solved by ngspice from its netlist, on
the model spice2rnm generated from that netlist, with their difference
underneath. Drag across a plot to zoom in. The data is inside each page,
so it works offline once loaded and installs nothing.</p>
<ul>
$rows</ul>
<p>How each figure was measured, and the circuits themselves, are in the
<a href="https://github.com/vrajeshprakhya/spice2rnm-demos">spice2rnm-demos repository</a>.</p>
</main>
</body>
</html>
EOF
echo "build_pages.sh: $n page(s) -> $OUT"
