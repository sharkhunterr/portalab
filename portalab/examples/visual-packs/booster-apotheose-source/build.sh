#!/usr/bin/env bash
# Rebuilds the Apothéose pack: its stylesheets and manifests (gen_pack.py), its stage's looping video (from
# stage.glsl), and its animations — built in EffectCraft (https://github.com/storytold/effectcraft, 0.18) on the
# manga toolkit, in slices of frames side by side, rendered at 24 fps and made into the videos its parts play
# (../tools/alpha_video.py: H.264, transparency beside the picture; ffmpeg). Each rarity's reveal takes the whole
# screen: square videos (1440) cropped to cover it, behind the card and over it.
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh [comp…]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
pack="$here/../booster-apotheose/elements"
video="$here/../tools/alpha_video.py"
core="$here/../booster-manga-source/effectcraft/core.jsx"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="${APO_WORK:-$(mktemp -d)}"
[ -n "${APO_WORK:-}" ] || trap 'rm -rf "$work"' EXIT
declare -A LENGTH=([opening]=64 [reveal-rare]=76 [reveal-epic]=92 [reveal-legendary]=110 [over-rare]=76 [over-epic]=92 [over-legendary]=110)
SLICE=16
scale="${SCALE:-1.3334}"
comps=("$@"); [ ${#comps[@]} -gt 0 ] || comps=(opening reveal-rare reveal-epic reveal-legendary over-rare over-epic over-legendary)
if [ $# -eq 0 ]; then
  python3 "$here/gen_pack.py"
  node "$here/../tools/stage_video.mjs" "$here/stage.glsl" "$pack/backdrop-apotheose/stage.mp4"
fi
slice() {
  local comp="$1" from="$2" to="$3" name="$1-$2"
  { echo "var ONLY = \"$comp\", FROM = $from, TO = $to, S = $scale;"; cat "$core" "$here/effectcraft/apotheose.jsx"; } > "$work/$name.jsx"
  "$cli" script "$work/$name.jsx" --empty --save-as "$work/$name.ecproj" > /dev/null
  mkdir -p "$work/slices/$name"
  "$cli" render --project "$work/$name.ecproj" --comp "$comp" --out "$work/slices/$name/f_[####].png" --format png --channels rgba > /dev/null
  for ((k = from; k < to; k++)); do mv "$work/slices/$name/$(printf 'f_%04d.png' "$k")" "$work/$comp/"; done
  rm -rf "$work/slices/$name" "$work/$name.ecproj"
}
export -f slice; export here work cli scale core
jobs=()
for comp in "${comps[@]}"; do
  rm -rf "${work:?}/$comp"; mkdir -p "$work/$comp"
  for ((from = 0; from < LENGTH[$comp]; from += SLICE)); do
    to=$((from + SLICE)); ((to > LENGTH[$comp])) && to=${LENGTH[$comp]}
    jobs+=("$comp $from $to")
  done
done
printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-4}" -L 1 bash -c 'slice "$0" "$1" "$2"'
for comp in "${comps[@]}"; do
  case "$comp" in
    opening) python3 "$video" "$pack/opening-apotheose/opening.mp4" "$work/opening" --crf 20 ;;
    reveal-*) python3 "$video" "$pack/$comp/reveal.mp4" "$work/$comp" --crf 21 ;;
    over-*) python3 "$video" "$pack/reveal-${comp#over-}/over.mp4" "$work/$comp" --crf 21 ;;
  esac
done
