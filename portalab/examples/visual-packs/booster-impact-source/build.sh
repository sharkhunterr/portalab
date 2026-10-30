#!/usr/bin/env bash
# Rebuilds the Impact pack's drawn parts: its SVG shapes and card faces, and its four animations — built in
# EffectCraft (https://github.com/storytold/effectcraft, 0.18), rendered on twos (12 fps, PNG with alpha) and
# assembled into the sprite sheets its stylesheets play.
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
pack="$here/../booster-impact"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
python3 "$here/gen_svgs.py" "$pack/elements"
python3 "$here/gen_faces.py" "$pack/elements"
for comp in opening reveal-rare reveal-epic reveal-legendary; do
  # EffectCraft's scripts read no other file: the helpers go into the one script
  { echo "var ONLY = \"$comp\";"; cat "$here/effectcraft/lib.jsx" "$here/effectcraft/impact.jsx"; } > "$work/$comp.jsx"
  "$cli" script "$work/$comp.jsx" --empty --save-as "$work/$comp.ecproj"
  mkdir -p "$work/frames/$comp"
  "$cli" render --project "$work/$comp.ecproj" --comp "$comp" --out "$work/frames/$comp/f_[####].png" --format png --channels rgba
done
python3 "$here/sheets.py" "$work/frames" "$pack"
