#!/usr/bin/env bash
# Rebuilds the Géode pack's drawn parts: its SVG shapes and card faces, and its animations — built in EffectCraft
# (https://github.com/storytold/effectcraft, 0.18) in slices of frames side by side, rendered at 24 fps (PNG with
# alpha) and made into the videos its parts play (../tools/alpha_video.py: H.264, transparency beside the
# picture; ffmpeg).
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh [comp…]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
pack="$here/../booster-geode/elements"
video="$here/../tools/alpha_video.py"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="${GEODE_WORK:-$(mktemp -d)}"   # GEODE_WORK keeps the renders (the videos alone can then be made again)
[ -n "${GEODE_WORK:-}" ] || trap 'rm -rf "$work"' EXIT
declare -A LENGTH=([opening]=64 [reveal-rare]=44 [reveal-epic]=58 [legendary]=72 [legendary-over]=72)
SLICE=16
comps=("$@"); [ ${#comps[@]} -gt 0 ] || comps=(opening reveal-rare reveal-epic legendary legendary-over)
if [ $# -eq 0 ]; then python3 "$here/gen_svgs.py" "$pack"; python3 "$here/gen_faces.py" "$pack"; fi
slice() {   # builds and renders one slice of a comp: its frames from..to-1
  local comp="$1" from="$2" to="$3" name="$1-$2"
  { echo "var ONLY = \"$comp\", FROM = $from, TO = $to;"; cat "$here/effectcraft/lib.jsx" "$here/effectcraft/geode.jsx"; } > "$work/$name.jsx"
  "$cli" script "$work/$name.jsx" --empty --save-as "$work/$name.ecproj" > /dev/null
  mkdir -p "$work/slices/$name"
  "$cli" render --project "$work/$name.ecproj" --comp "$comp" --out "$work/slices/$name/f_[####].png" --format png --channels rgba > /dev/null
  for ((k = from; k < to; k++)); do mv "$work/slices/$name/$(printf 'f_%04d.png' "$k")" "$work/frames/$comp/"; done
}
export -f slice; export here work cli
jobs=()
for comp in "${comps[@]}"; do
  rm -rf "$work/frames/$comp"; mkdir -p "$work/frames/$comp"
  for ((from = 0; from < LENGTH[$comp]; from += SLICE)); do
    to=$((from + SLICE)); ((to > LENGTH[$comp])) && to=${LENGTH[$comp]}
    jobs+=("$comp $from $to")
  done
done
printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-4}" -L 1 bash -c 'slice "$0" "$1" "$2"'
f="$work/frames"
for comp in "${comps[@]}"; do
  case "$comp" in
    opening) python3 "$video" "$pack/opening-geode/opening.mp4" "$f/opening" ;;
    reveal-rare) python3 "$video" "$pack/reveal-rare/reveal.mp4" "$f/reveal-rare" ;;
    reveal-epic) python3 "$video" "$pack/reveal-epic/reveal.mp4" "$f/reveal-epic" ;;
    legendary) python3 "$video" "$pack/reveal-legendary/reveal.mp4" "$f/legendary" ;;
    legendary-over) python3 "$video" "$pack/reveal-legendary/over.mp4" "$f/legendary-over" ;;
  esac
done
