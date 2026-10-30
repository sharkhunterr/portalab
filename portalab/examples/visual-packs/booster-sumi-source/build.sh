#!/usr/bin/env bash
# Rebuilds the Sumi pack's drawn parts: its SVG shapes and card faces, and its animations — built in EffectCraft
# (https://github.com/storytold/effectcraft, 0.18), rendered at 24 fps (PNG with alpha) and made into the
# videos its parts play (../tools/alpha_video.py: H.264, transparency stacked under the picture; ffmpeg).
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
pack="$here/../booster-sumi/elements"
video="$here/../tools/alpha_video.py"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="${SUMI_WORK:-$(mktemp -d)}"   # SUMI_WORK keeps the renders (the videos alone can then be made again)
[ -n "${SUMI_WORK:-}" ] || trap 'rm -rf "$work"' EXIT
python3 "$here/gen_svgs.py" "$pack"
python3 "$here/gen_faces.py" "$pack"
render() {
  # EffectCraft's scripts read no other file: the helpers go into the one script
  local comp="$1"
  { echo "var ONLY = \"$comp\";"; cat "$here/effectcraft/lib.jsx" "$here/effectcraft/sumi.jsx"; } > "$work/$comp.jsx"
  "$cli" script "$work/$comp.jsx" --empty --save-as "$work/$comp.ecproj"
  mkdir -p "$work/frames/$comp"
  "$cli" render --project "$work/$comp.ecproj" --comp "$comp" --out "$work/frames/$comp/f_[####].png" --format png --channels rgba
}
# the comps are independent: built side by side
for comp in opening reveal-rare reveal-epic reveal-legendary legendary-front legendary-back; do render "$comp" & done
wait
f="$work/frames"
python3 "$video" "$pack/opening-sumi/opening.mp4" "$f/opening"
python3 "$video" "$pack/reveal-rare/reveal.mp4" "$f/reveal-rare"
python3 "$video" "$pack/reveal-epic/reveal.mp4" "$f/reveal-epic"
# the legendary: its dragon from the start, behind the card (and over it, its second video); its reveal from
# when the dragon soars away (2/3 s), the whole within 3 s
python3 "$video" "$pack/reveal-legendary/reveal.mp4" "$f/reveal-legendary@16" "$f/legendary-back" --length 72
python3 "$video" "$pack/reveal-legendary/over.mp4" "$f/legendary-front"
