#!/usr/bin/env bash
# Rebuilds the manga universe's four scene packs (booster-shonen, -magical, -ninja, -mecha): their SVG shapes,
# stylesheets and manifests (gen_packs.py), and their animations — built in EffectCraft
# (https://github.com/storytold/effectcraft, 0.18) in slices of frames side by side, at 1.5 times the scenes'
# size (SCALE), rendered at 24 fps (PNG with alpha) and made into the videos their parts play
# (../tools/alpha_video.py: H.264, transparency beside the picture; ffmpeg).
#   EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh [style [comp…]]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
video="$here/../tools/alpha_video.py"
cli="${EFFECTCRAFT:-effectcraft-cli}"
work="${MANGA_WORK:-$(mktemp -d)}"   # MANGA_WORK keeps the renders (the videos alone can then be made again)
[ -n "${MANGA_WORK:-}" ] || trap 'rm -rf "$work"' EXIT
declare -A LENGTH=([opening]=64 [reveal-rare]=44 [reveal-epic]=58 [legendary]=72 [legendary-over]=72)
SLICE=16
scale="${SCALE:-1.5}"
styles=("${1:-}"); [ -n "${1:-}" ] || styles=(shonen magical ninja mecha)
shift || true
comps=("$@"); [ ${#comps[@]} -gt 0 ] || comps=(opening reveal-rare reveal-epic legendary legendary-over)
[ $# -gt 0 ] || python3 "$here/gen_packs.py"
slice() {   # builds and renders one slice of one style's comp: its frames from..to-1
  local style="$1" comp="$2" from="$3" to="$4" name="$1-$2-$3"
  { echo "var ONLY = \"$comp\", FROM = $from, TO = $to, S = $scale;"; cat "$here/effectcraft/core.jsx" "$here/effectcraft/$style.jsx"; } > "$work/$name.jsx"
  "$cli" script "$work/$name.jsx" --empty --save-as "$work/$name.ecproj" > /dev/null
  mkdir -p "$work/slices/$name"
  "$cli" render --project "$work/$name.ecproj" --comp "$comp" --out "$work/slices/$name/f_[####].png" --format png --channels rgba > /dev/null
  for ((k = from; k < to; k++)); do mv "$work/slices/$name/$(printf 'f_%04d.png' "$k")" "$work/$style/$comp/"; done
  rm -rf "$work/slices/$name" "$work/$name.ecproj"
}
export -f slice; export here work cli scale
jobs=()
for style in "${styles[@]}"; do
  for comp in "${comps[@]}"; do
    rm -rf "${work:?}/$style/$comp"; mkdir -p "$work/$style/$comp"
    for ((from = 0; from < LENGTH[$comp]; from += SLICE)); do
      to=$((from + SLICE)); ((to > LENGTH[$comp])) && to=${LENGTH[$comp]}
      jobs+=("$style $comp $from $to")
    done
  done
done
printf '%s\n' "${jobs[@]}" | xargs -P "${JOBS:-4}" -L 1 bash -c 'slice "$0" "$1" "$2" "$3"'
for style in "${styles[@]}"; do
  pack="$here/../booster-$style/elements" f="$work/$style"
  # its stage: the GLSL played as a looping video (Playwright's Chromium from the frontend's dependencies)
  [ $# -gt 0 ] || node "$here/../tools/stage_video.mjs" "$here/stages/$style.glsl" "$pack/backdrop-$style/stage.mp4"
  for comp in "${comps[@]}"; do
    case "$comp" in
      opening) python3 "$video" "$pack/opening-$style/opening.mp4" "$f/opening" --crf 19 ;;
      reveal-rare) python3 "$video" "$pack/reveal-rare/reveal.mp4" "$f/reveal-rare" --crf 19 ;;
      reveal-epic) python3 "$video" "$pack/reveal-epic/reveal.mp4" "$f/reveal-epic" --crf 19 ;;
      legendary) python3 "$video" "$pack/reveal-legendary/reveal.mp4" "$f/legendary" --crf 19 ;;
      legendary-over) python3 "$video" "$pack/reveal-legendary/over.mp4" "$f/legendary-over" --crf 19 ;;
    esac
  done
done
