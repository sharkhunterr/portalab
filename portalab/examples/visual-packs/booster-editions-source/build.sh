#!/usr/bin/env bash
# Rebuilds the edition scene packs (booster-ed-<edition>, one per media card edition): their stylesheets and
# manifests (gen_editions.py), their stages' looping videos (stages/<edition>.glsl), and their animations — built
# in EffectCraft (https://github.com/storytold/effectcraft, 0.18) on the manga toolkit, in slices of frames side by
# side, at 1.33 times (SCALE), rendered at 24 fps and made into the videos their parts play (../tools/alpha_video.py;
# ffmpeg). Every rarity's reveal takes the whole screen: square videos (1440).
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh [edition [comp…]]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
video="$here/../tools/alpha_video.py"
core="$here/../booster-manga-source/effectcraft/core.jsx"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="${EDITIONS_WORK:-$(mktemp -d)}"
[ -n "${EDITIONS_WORK:-}" ] || trap 'rm -rf "$work"' EXIT
declare -A LENGTH=([opening]=64 [reveal-rare]=76 [reveal-epic]=92 [reveal-legendary]=110 [over-rare]=76 [over-epic]=92 [over-legendary]=110)
SLICE=16
scale="${SCALE:-1.3334}"
keys=("${1:-}"); [ -n "${1:-}" ] || keys=(nitrate noir drivein super8 film laserdisc vhs zine bubble disc leather tiles stream glass)
shift || true
comps=("$@"); [ ${#comps[@]} -gt 0 ] || comps=(opening reveal-rare reveal-epic reveal-legendary over-rare over-epic over-legendary)
if [ $# -eq 0 ]; then
  python3 "$here/gen_editions.py"
  for key in "${keys[@]}"; do node "$here/../tools/stage_video.mjs" "$here/stages/$key.glsl" "$here/../booster-ed-$key/elements/backdrop-ed-$key/stage.mp4"; done
fi
slice() {
  local key="$1" comp="$2" from="$3" to="$4" name="$1-$2-$3"
  { echo "var ONLY = \"$comp\", EDITION_KEY = \"$key\", FROM = $from, TO = $to, S = $scale;"; cat "$core" "$here/effectcraft/editions.jsx"; } > "$work/$name.jsx"
  "$cli" script "$work/$name.jsx" --empty --save-as "$work/$name.ecproj" > /dev/null
  mkdir -p "$work/slices/$name"
  "$cli" render --project "$work/$name.ecproj" --comp "$comp" --out "$work/slices/$name/f_[####].png" --format png --channels rgba > /dev/null
  for ((k = from; k < to; k++)); do mv "$work/slices/$name/$(printf 'f_%04d.png' "$k")" "$work/$key/$comp/"; done
  rm -rf "$work/slices/$name" "$work/$name.ecproj"
}
export -f slice; export here work cli scale core
jobs=()
for key in "${keys[@]}"; do
  for comp in "${comps[@]}"; do
    rm -rf "${work:?}/$key/$comp"; mkdir -p "$work/$key/$comp"
    for ((from = 0; from < LENGTH[$comp]; from += SLICE)); do
      to=$((from + SLICE)); ((to > LENGTH[$comp])) && to=${LENGTH[$comp]}
      jobs+=("$key $comp $from $to")
    done
  done
done
printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-4}" -L 1 bash -c 'slice "$0" "$1" "$2" "$3"'
for key in "${keys[@]}"; do
  pack="$here/../booster-ed-$key/elements" f="$work/$key"
  for comp in "${comps[@]}"; do
    case "$comp" in
      opening) python3 "$video" "$pack/opening-ed-$key/opening.mp4" "$f/opening" --crf 20 ;;
      reveal-*) python3 "$video" "$pack/$comp/reveal.mp4" "$f/$comp" --crf 21 ;;
      over-*) python3 "$video" "$pack/reveal-${comp#over-}/over.mp4" "$f/$comp" --crf 21 ;;
    esac
  done
done
