"""Makes a pack's video from frames — PNG with transparency, 24 a second — for a scene part of ``kind: video``
with ``alpha: side`` (or ``stacked``, issue 287): the picture in the left (upper) half — premultiplied: black
where it is transparent —, its transparency in grey in the right (lower) half, as an H.264 MP4 every browser
plays on its hardware decoder (side by side, a tall layer's video stays within the 4K phones decode). Several frame folders are laid one over the other (the first at the bottom), each from the video's
first frame or from a later one (``FRAMES@12``: from its 12th), transparent before and after. Needs ffmpeg.

    alpha_video.py OUT.mp4 FRAMES[@START] [FRAMES[@START]…] [--scale 0.75] [--crf 20] [--fps 24] [--length 72] [--layout side|stacked]
"""

import argparse
import re
import subprocess
from pathlib import Path


def frames_pattern(folder: Path) -> str:
    """``f_%04d.png`` for frames numbered like EffectCraft's (``f_0000.png``…)."""
    first = re.fullmatch(r"(.*?)(\d+)\.png", sorted(folder.glob("*.png"))[0].name)
    if first is None:
        raise SystemExit(f"{folder}: no numbered frames")
    return str(folder / f"{first[1]}%0{len(first[2])}d.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("frames", nargs="+")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--length", type=int, default=0, help="at most this many frames")
    parser.add_argument("--layout", choices=("side", "stacked"), default="side")
    parser.add_argument("--max-kb", type=int, default=4900, help="compressed a little more until it weighs less (a pack's file: 5 MB)")
    args = parser.parse_args()
    layers = []
    for given in args.frames:
        folder, _, start = given.partition("@")
        layers.append((Path(folder), int(start or 0), len(list(Path(folder).glob("*.png")))))
    total = max(start + count for _, start, count in layers)
    longest = total
    inputs: list[str] = []
    for folder, _, _ in layers:
        inputs += ["-framerate", str(args.fps), "-start_number", "0", "-i", frames_pattern(folder)]
    # each layer as long as the video (transparent before it starts and after it ends), one over the other;
    # then the picture premultiplied over its transparency, both even-sized
    pads = [f"[{k}:v]format=rgba,tpad=start={start}:stop={longest - start - count}:color=black@0[p{k}]"
            for k, (_, start, count) in enumerate(layers)]  # fmt: skip
    graph = ";".join(pads) + ";[p0]null[l0]"
    for k in range(1, len(layers)):
        graph += f";[l{k - 1}][p{k}]overlay=format=auto,format=rgba[l{k}]"
    last = f"l{len(layers) - 1}"
    size = f"trunc(iw*{args.scale}/2)*2:trunc(ih*{args.scale}/2)*2"
    graph += (
        f";[{last}]scale={size}:flags=lanczos,split[c][a]"
        ";[c]format=rgba,premultiply=inplace=1,format=gbrp[picture]"
        ";[a]format=rgba,alphaextract,format=gray,format=gbrp[alpha]"
        f";[picture][alpha]{'hstack' if args.layout == 'side' else 'vstack'},format=yuv420p"
        f",trim=end_frame={args.length or longest}[out]"
    )
    crf = args.crf
    while True:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[out]",
             "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-tune", "animation",
             "-r", str(args.fps), "-movflags", "+faststart", "-an", str(args.out)],
            check=True,
        )  # fmt: skip
        if args.out.stat().st_size <= args.max_kb * 1024 or crf >= 32:
            break
        crf += 2
    print(f"{args.out.name}: {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
