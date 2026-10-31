#!/usr/bin/env bash
# Rebuilds the genre scene packs (booster-blockbuster, -tenebres, -rideau, -arcanes, -hyperespace): their
# stylesheets and manifests (gen_genres.py), their stages' looping videos (stages/<key>.glsl), and their
# animations — built in EffectCraft (https://github.com/storytold/effectcraft, 0.18) on the manga toolkit, in
# slices of frames side by side, at 1.33 times (SCALE), rendered at 24 fps and made into the videos their parts
# play (../tools/alpha_video.py; ffmpeg). Every rarity's reveal takes the whole screen: square videos (1440).
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh [key [comp…]]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
video="$here/../tools/alpha_video.py"
core="$here/../booster-manga-source/effectcraft/core.jsx"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="${GENRES_WORK:-$(mktemp -d)}"
[ -n "${GENRES_WORK:-}" ] || trap 'rm -rf "$work"' EXIT
declare -A FAMILY=([blockbuster]=action [tenebres]=dark [rideau]=drama [arcanes]=fantasy [hyperespace]=sf)
declare -A LENGTH=([opening]=64 [reveal-rare]=76 [reveal-epic]=92 [reveal-legendary]=110 [over-rare]=76 [over-epic]=92 [over-legendary]=110)
SLICE=16
scale="${SCALE:-1.3334}"
keys=("${1:-}"); [ -n "${1:-}" ] || keys=(blockbuster tenebres rideau arcanes hyperespace)
shift || true
comps=("$@"); [ ${#comps[@]} -gt 0 ] || comps=(opening reveal-rare reveal-epic reveal-legendary over-rare over-epic over-legendary)
if [ $# -eq 0 ]; then
  python3 "$here/gen_genres.py"
  for key in "${keys[@]}"; do node "$here/../tools/stage_video.mjs" "$here/stages/$key.glsl" "$here/../booster-$key/elements/backdrop-$key/stage.mp4"; done
fi
slice() {
  local key="$1" comp="$2" from="$3" to="$4" name="$1-$2-$3"
  { echo "var ONLY = \"$comp\", GENRE_KEY = \"${FAMILY[$key]}\", FROM = $from, TO = $to, S = $scale;"; cat "$core" "$here/effectcraft/genres.jsx"; } > "$work/$name.jsx"
  "$cli" script "$work/$name.jsx" --empty --save-as "$work/$name.ecproj" > /dev/null
  mkdir -p "$work/slices/$name"
  "$cli" render --project "$work/$name.ecproj" --comp "$comp" --out "$work/slices/$name/f_[####].png" --format png --channels rgba > /dev/null
  for ((k = from; k < to; k++)); do mv "$work/slices/$name/$(printf 'f_%04d.png' "$k")" "$work/$key/$comp/"; done
  rm -rf "$work/slices/$name" "$work/$name.ecproj"
}
export -f slice; export here work cli scale core
export FAMILY_DECL="$(declare -p FAMILY)"
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
printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-4}" -L 1 bash -c 'eval "$FAMILY_DECL"; slice "$0" "$1" "$2" "$3"'
for key in "${keys[@]}"; do
  pack="$here/../booster-$key/elements" f="$work/$key"
  for comp in "${comps[@]}"; do
    case "$comp" in
      opening) python3 "$video" "$pack/opening-$key/opening.mp4" "$f/opening" --crf 20 ;;
      reveal-*) python3 "$video" "$pack/$comp/reveal.mp4" "$f/$comp" --crf 21 ;;
      over-*) python3 "$video" "$pack/reveal-${comp#over-}/over.mp4" "$f/$comp" --crf 21 ;;
    esac
  done
done
