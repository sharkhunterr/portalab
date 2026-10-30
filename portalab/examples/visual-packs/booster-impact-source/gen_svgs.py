"""Draws the Impact pack's comic shapes as SVG: thick ink outlines, flat cel colours, jagged and brushy edges."""

import math
import random
import sys
from pathlib import Path

INK = "#12061c"
PINK = "#ff2d8f"
PINK_LIGHT = "#ff8ccc"
WHITE = "#ffffff"
VIOLET = "#6a22c9"
VIOLET_DARK = "#2a0b57"
MAGENTA = "#d21dc4"
GREEN = "#2bff6e"
GREEN_DARK = "#0aa63f"
GREEN_LIGHT = "#b8ff9a"
LIME = "#d4f53c"
LIME_DARK = "#6f9400"
YELLOW = "#ffd21f"


def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>\n'


def poly(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def star(cx, cy, n, r_out, r_in, rng, jitter=0.25, spread=0.18, turn=0.0):
    pts = []
    for i in range(n * 2):
        a = turn + i / (n * 2) * math.tau + rng.uniform(-jitter, jitter) / n
        r = (r_out * rng.uniform(1 - spread, 1.0)) if i % 2 == 0 else (r_in * rng.uniform(0.85, 1.1))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def outlined(d, fill, width, extra=""):
    return (f'<path d="{d}" fill="{fill}" stroke="{INK}" stroke-width="{width}" stroke-linejoin="round" '
            f'paint-order="stroke" {extra}/>')


def burst():
    """A manga impact burst: a pink star of uneven spikes, a white one inside, inked."""
    rng = random.Random(7)
    outer = poly(star(400, 400, 22, 390, 150, rng, spread=0.42))
    inner = poly(star(400, 400, 16, 250, 95, rng, spread=0.38, turn=0.1))
    core = poly(star(400, 400, 12, 120, 60, rng, spread=0.3))
    return svg(800, 800, outlined(outer, PINK, 14) + outlined(inner, WHITE, 10) + f'<path d="{core}" fill="{PINK_LIGHT}"/>')


def slash(seed, bend):
    """A white brush slash: fat in its first third, tapering to a point, its trailing edge torn into teeth;
    a pink rim under it, inked."""
    rng = random.Random(seed)
    w, h = 1200, 460
    top, bottom = [], []
    steps = 70
    for i in range(steps + 1):
        x = i / steps
        width = math.sin(math.pi * x ** 0.55) ** 0.7 * 150
        y = h / 2 + bend * (math.sin(math.pi * x) - 0.5) * 120
        top.append((40 + x * (w - 80), y - width * rng.uniform(0.9, 1.0)))
        tooth = width * (rng.uniform(0.35, 1.0) if i % 2 else 1.0) if x < 0.7 else width
        bottom.append((40 + x * (w - 80), y + tooth))
    d = poly(top + bottom[::-1])
    rim = poly([(x + 10, y + 16) for x, y in top + bottom[::-1]])
    return svg(w, h, f'<path d="{rim}" fill="{PINK}"/>' + outlined(d, WHITE, 10))


def zap():
    """Pink lightning crackling round a card: jagged strokes on its four sides, inked, a white core."""
    rng = random.Random(11)
    w, h = 400, 520
    cx0, cy0, cx1, cy1 = 70, 70, 330, 450
    paths = []
    for side in range(4):
        for k in range(2):
            pts = []
            n = 9
            for i in range(n + 1):
                t = i / n
                off = rng.uniform(14, 44) * (1 if i % 2 else 0.4)
                if side == 0:
                    pts.append((cx0 + (cx1 - cx0) * t, cy0 - off))
                elif side == 1:
                    pts.append((cx1 + off, cy0 + (cy1 - cy0) * t))
                elif side == 2:
                    pts.append((cx1 - (cx1 - cx0) * t, cy1 + off))
                else:
                    pts.append((cx0 - off, cy1 - (cy1 - cy0) * t))
            start = rng.randint(0, 3)
            pts = pts[start:start + rng.randint(6, 9)]
            d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            paths.append(d)
    body = "".join(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="30" stroke-linejoin="miter" stroke-linecap="round"/>' for d in paths)
    body += "".join(f'<path d="{d}" fill="none" stroke="{PINK}" stroke-width="18" stroke-linejoin="miter" stroke-linecap="round"/>' for d in paths)
    body += "".join(f'<path d="{d}" fill="none" stroke="{WHITE}" stroke-width="5" stroke-linejoin="miter" stroke-linecap="round"/>' for d in paths)
    return svg(w, h, body)


def slime():
    """Toxic goo wrapping a card: a blobby band round it, drips falling from its foot and splashes, its
    highlights, inked inside and out (the middle cut out: the card shows through)."""
    rng = random.Random(23)
    w, h = 400, 520
    x0, y0, x1, y1 = 60, 60, 340, 460      # the card's place
    pts = []
    perimeter = []
    n = 160
    for i in range(n):
        t = i / n
        # walk the rectangle's outline
        L = 2 * ((x1 - x0) + (y1 - y0))
        s = t * L
        if s < x1 - x0:
            p, nrm = (x0 + s, y0), (0, -1)
        elif s < (x1 - x0) + (y1 - y0):
            p, nrm = (x1, y0 + s - (x1 - x0)), (1, 0)
        elif s < 2 * (x1 - x0) + (y1 - y0):
            p, nrm = (x1 - (s - (x1 - x0) - (y1 - y0)), y1), (0, 1)
        else:
            p, nrm = (x0, y1 - (s - 2 * (x1 - x0) - (y1 - y0))), (-1, 0)
        perimeter.append((p, nrm))
    phase = [rng.uniform(0, math.tau) for _ in range(4)]
    for i, (p, nrm) in enumerate(perimeter):
        t = i / n
        bulge = 16 + 9 * math.sin(t * 23 + phase[0]) + 6 * math.sin(t * 57 + phase[1])
        if nrm == (0, 1):            # drips hanging from the foot
            for c in (0.2, 0.47, 0.71, 0.88):
                d = abs((p[0] - x0) / (x1 - x0) - c)
                bulge += max(0.0, 1 - d / 0.035) * rng.uniform(30, 60) if d < 0.035 else 0
        pts.append((p[0] + nrm[0] * bulge, p[1] + nrm[1] * bulge))
    inner = []
    for i, (p, nrm) in enumerate(perimeter):
        t = i / n
        dip = 4 + 2.5 * math.sin(t * 31 + phase[2]) + 1.5 * math.sin(t * 71 + phase[3])
        inner.append((p[0] - nrm[0] * dip, p[1] - nrm[1] * dip))
    d = poly(pts) + " " + poly(inner[::-1])
    body = f'<path d="{d}" fill="{GREEN}" fill-rule="evenodd" stroke="{INK}" stroke-width="10" stroke-linejoin="round" paint-order="stroke"/>'
    # darker cel shade along its outer half, light highlights
    shade = poly([(x + (x - 200) * -0.02, y + 6) for x, y in pts]) + " " + poly(inner[::-1])
    body += f'<path d="{shade}" fill="{GREEN_DARK}" fill-rule="evenodd" opacity="0.45" clip-path="none"/>'
    for _ in range(26):
        i = rng.randrange(n)
        (p, nrm) = perimeter[i]
        r = rng.uniform(3, 7)
        body += f'<ellipse cx="{p[0] + nrm[0] * 6:.1f}" cy="{p[1] + nrm[1] * 6:.1f}" rx="{r * 1.6:.1f}" ry="{r:.1f}" fill="{GREEN_LIGHT}"/>'
    # splashes flying off
    for _ in range(9):
        i = rng.randrange(n)
        (p, nrm) = perimeter[i]
        dist = rng.uniform(34, 60)
        r = rng.uniform(5, 11)
        body += outlined(f"M{p[0] + nrm[0] * dist - r:.1f},{p[1] + nrm[1] * dist:.1f} a{r:.1f},{r:.1f} 0 1,0 {2 * r:.1f},0 a{r:.1f},{r:.1f} 0 1,0 {-2 * r:.1f},0", GREEN, 5)
    return svg(w, h, body)


def glint():
    """A great four-pointed glint, white, inked, with a small pink one beside it."""
    def four(cx, cy, r, k):
        return (f"M{cx},{cy - r} Q{cx + r * k},{cy - r * k} {cx + r},{cy} Q{cx + r * k},{cy + r * k} {cx},{cy + r} "
                f"Q{cx - r * k},{cy + r * k} {cx - r},{cy} Q{cx - r * k},{cy - r * k} {cx},{cy - r} Z")
    return svg(400, 400, outlined(four(200, 200, 180, 0.12), WHITE, 10) + outlined(four(330, 90, 46, 0.14), PINK, 6))


def binary():
    """A tile of bold slanted binary digits, dark lime: the legendary's wall."""
    rng = random.Random(5)
    w, h = 240, 160
    body = ""
    for row in range(2):
        for col in range(4):
            x, y = 14 + col * 58, 10 + row * 78
            if rng.random() < 0.5:
                body += f'<rect x="{x + 6}" y="{y}" width="34" height="62" rx="15" fill="none" stroke="{LIME_DARK}" stroke-width="11"/>'
            else:
                body += f'<path d="M{x + 14},{y + 14} L{x + 26},{y} L{x + 34},{y} L{x + 34},{y + 62} L{x + 22},{y + 62} L{x + 22},{y + 18} Z" fill="{LIME_DARK}"/>'
    return svg(w, h, f'<g transform="skewX(-14) translate(20 0)">{body}</g>')


def emblem():
    """An original emblem: a tilted, rounded hexagon in magenta and violet, a white bolt through it, inked."""
    pts = [(200 + 160 * math.cos(math.tau * i / 6 + math.pi / 6), 200 + 160 * math.sin(math.tau * i / 6 + math.pi / 6)) for i in range(6)]
    hexa = poly(pts)
    inner = poly([(200 + 112 * math.cos(math.tau * i / 6 + math.pi / 6), 200 + 112 * math.sin(math.tau * i / 6 + math.pi / 6)) for i in range(6)])
    bolt = "M222,92 L146,214 L196,214 L170,312 L258,178 L206,178 Z"
    return svg(400, 400, (f'<g transform="rotate(-8 200 200)">' + outlined(hexa, MAGENTA, 18) +
                          f'<path d="{hexa}" fill="{VIOLET}" transform="translate(14 16) scale(0.93)" opacity="0.55"/>' +
                          outlined(inner, VIOLET_DARK, 10) + outlined(bolt, WHITE, 12) +
                          f'<path d="M78,150 L120,104" stroke="{WHITE}" stroke-width="10" stroke-linecap="round" opacity="0.8"/></g>'))


def doodles():
    """Graffiti doodles in a tile: hearts, stars, a skull, an arrow, crosses and a squiggle — white chalk."""
    s = f'fill="none" stroke="{WHITE}" stroke-opacity="0.2" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"'
    body = (f'<path {s} d="M40,60 C40,40 70,40 70,60 C70,40 100,40 100,60 C100,85 70,100 70,110 C70,100 40,85 40,60 Z"/>'
            f'<path {s} d="M210,40 L220,70 L250,70 L226,88 L236,118 L210,100 L184,118 L194,88 L170,70 L200,70 Z"/>'
            f'<circle {s} cx="80" cy="200" r="34"/><circle cx="66" cy="196" r="8" fill="{WHITE}" fill-opacity="0.2"/><circle cx="94" cy="196" r="8" fill="{WHITE}" fill-opacity="0.2"/>'
            f'<path {s} d="M66,226 L66,240 M80,226 L80,240 M94,226 L94,240"/>'
            f'<path {s} d="M160,200 C190,170 220,230 250,200 C270,180 280,210 290,200"/>'
            f'<path {s} d="M150,270 L230,250 M212,236 L232,250 L214,266"/>'
            f'<path {s} d="M20,280 L44,304 M44,280 L20,304"/><path {s} d="M262,140 L282,160 M282,140 L262,160"/>')
    return svg(300, 320, body)


TARGETS = {
    "burst.svg": (burst, []),
    "slash-a.svg": (lambda: slash(1, 1), ["face-epic"]),
    "slash-b.svg": (lambda: slash(2, -1), []),
    "zap.svg": (zap, []),
    "slime.svg": (slime, ["face-legendary"]),
    "glint.svg": (glint, ["look-impact"]),
    "binary.svg": (binary, ["face-legendary"]),
    "emblem.svg": (emblem, ["look-impact", "back-impact"]),
    "doodles.svg": (doodles, ["look-impact", "back-impact"]),
}

if __name__ == "__main__":
    root = Path(sys.argv[1])
    for name, (draw, elements) in TARGETS.items():
        text = draw()
        for element in elements:
            (root / element / name).write_text(text)
    print("drawn", len(TARGETS))
