"""Draws the Sumi pack's still shapes as SVG — washi paper, brushed ink, gold leaf, cords and patterns — and writes
each into the elements that use it."""

import math
import random
import sys
from pathlib import Path

INK = "#0e0a09"
GOLD = "#d9a43a"
GOLD_LIGHT = "#ffe09a"
GOLD_DARK = "#8a560f"
SHU = "#d8321d"
SHU_DARK = "#7e1209"
WHITE = "#f8f1e1"
SAKURA = "#fcc0cf"
SAKURA_DARK = "#e57895"
SILVER = "#d9e2ee"


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'{"<defs>" + defs + "</defs>" if defs else ""}{body}</svg>\n')


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def resample(pts, m):
    lengths = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    total, out, j = lengths[-1] or 1, [], 1
    for k in range(m + 1):
        at = total * k / m
        while j < len(pts) - 1 and lengths[j] < at:
            j += 1
        t = (at - lengths[j - 1]) / ((lengths[j] - lengths[j - 1]) or 1)
        out.append((pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * t, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * t))
    return out


def brush(pts, width, rng, dry=0.55, bristles=11):
    """A brush stroke along a centre line — the same brush as the animations' (effectcraft/lib.jsx): a heavy round
    press where it lands, its weight swelling and easing, thinning to a point, its bristles running dry."""
    line = resample(pts, 160)
    n = len(line)
    ph, ph2 = rng.uniform(0, 6), rng.uniform(0, 6)
    normals, press = [], []
    for i in range(n):
        (ax, ay), (bx, by) = line[max(0, i - 1)], line[min(n - 1, i + 1)]
        tx, ty = bx - ax, by - ay
        length = math.hypot(tx, ty) or 1
        normals.append((-ty / length, tx / length))
        u = i / (n - 1)
        land = math.sqrt(min(1, u / 0.03)) * (1 + 0.38 * math.exp(-u * 22))
        press.append(width * 0.5 * land * (1 + 0.13 * math.sin(u * 7.5 + ph) + 0.06 * math.sin(u * 19 + ph2)) * (1 - u) ** 0.42)
    outlines = []
    for k in range(bristles):
        o = (k + 0.5) / bristles * 2 - 1
        h = 1.55 / bristles * rng.uniform(0.7, 1.2)
        stop = dry + (1 - dry) * (1 - abs(o) ** 1.2 * rng.uniform(0.35, 1)) * rng.uniform(0.7, 1)
        wph, wamp = rng.uniform(0, 6), rng.uniform(0.02, 0.06)
        pieces = [(rng.uniform(0, 0.02) * abs(o), stop)]
        for _ in range(2):
            if rng.random() < 0.55:
                at, gap = dry + (stop - dry) * rng.random(), rng.uniform(0.02, 0.07)
                a, b = pieces.pop()
                pieces += [(a, at), (at + gap, b)] if a < at and at + gap < b else [(a, b)]
        for u0, u1 in pieces:
            left, right = [], []
            for j in range(n):
                u = j / (n - 1)
                if u0 <= u <= u1:
                    c, w = o + wamp * math.sin(u * 13 + wph), press[j]
                    nx, ny = normals[j]
                    left.append((line[j][0] + nx * (c + h) * w, line[j][1] + ny * (c + h) * w))
                    right.append((line[j][0] + nx * (c - h) * w, line[j][1] + ny * (c - h) * w))
            if len(left) > 1:
                outlines.append(path(left + right[::-1]))
    return " ".join(outlines)


def enso_line(cx, cy, r, a0, sweep, k=1.0, m=90):
    return [(cx + math.cos(a0 + u * sweep) * r * (1 + 0.035 * math.sin(u * 7 + a0) - 0.05 * u),
             cy + math.sin(a0 + u * sweep) * r * k * (1 + 0.035 * math.sin(u * 7 + a0) - 0.05 * u))
            for u in (i / m for i in range(m + 1))]


def washi():
    """Washi paper: a warm fibrous grain, long pale fibres laid every way, a few darker flecks."""
    rng = random.Random(3)
    fibres = []
    for _ in range(90):
        x, y, a = rng.uniform(0, 400), rng.uniform(0, 400), rng.uniform(0, math.pi)
        pts = [(x, y)]
        for _ in range(6):
            a += rng.uniform(-0.5, 0.5)
            x, y = x + math.cos(a) * rng.uniform(6, 16), y + math.sin(a) * rng.uniform(6, 16)
            pts.append((x, y))
        fibres.append("M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts))
    flecks = "".join(f'<circle cx="{rng.uniform(0, 400):.1f}" cy="{rng.uniform(0, 400):.1f}" r="{rng.uniform(0.4, 1.3):.1f}"/>' for _ in range(40))
    defs = ('<filter id="g" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="4"/>'
            '<feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.36  0 0 0 0 0.25  0 0 0 0.16 0"/></filter>')
    return svg(400, 400, '<rect width="400" height="400" filter="url(#g)"/>'
               f'<path d="{" ".join(fibres)}" fill="none" stroke="#fffaf0" stroke-width="0.9" stroke-opacity="0.55" stroke-linecap="round"/>'
               f'<g fill="#6b5236" fill-opacity="0.35">{flecks}</g>', defs)


def band():
    """The pack's name band: one loaded horizontal stroke of ink, dry at its end, gilded underneath."""
    rng = random.Random(5)
    line = [(30 + 540 * u, 60 + 8 * math.sin(u * 3.0)) for u in (i / 60 for i in range(61))]
    d = brush(line, 104, rng, dry=0.78, bristles=16)
    return svg(600, 120, f'<path d="{d}" fill="{GOLD}" transform="translate(4,5)"/><path d="{d}" fill="{INK}"/>')


def enso(color, edge, seed, opacity=1.0):
    """An ensō: a circle drawn in one breath, edged."""
    rng = random.Random(seed)
    d = brush(enso_line(200, 200, 150, -2.1, math.pi * 1.82), 44, rng, dry=0.5, bristles=11)
    return svg(400, 400, f'<g opacity="{opacity}"><path d="{d}" fill="{edge}" transform="translate(4,5)"/><path d="{d}" fill="{color}"/></g>')


def mizuhiki():
    """Mizuhiki cords tied across the pack's crimp: red, white and gold cords, a double knot in the middle."""
    cords = []
    colors = [SHU, WHITE, GOLD, SHU, GOLD_LIGHT]
    for i, c in enumerate(colors):
        dy = (i - 2) * 4.2
        left = f"M0,{40 + dy:.1f} C80,{40 + dy:.1f} 120,{38 + dy:.1f} 160,{36 + dy * 1.2:.1f}"
        right = f"M240,{36 + dy * 1.2:.1f} C280,{38 + dy:.1f} 320,{40 + dy:.1f} 400,{40 + dy:.1f}"
        loop_l = f"M160,{36 + dy * 1.2:.1f} C176,{6 + dy * 2:.1f} 214,{6 + dy * 2:.1f} 200,{40 + dy:.1f} C186,{74 - dy * 2:.1f} 150,{70 - dy * 2:.1f} 172,{44 + dy:.1f}"
        loop_r = f"M240,{36 + dy * 1.2:.1f} C224,{6 + dy * 2:.1f} 186,{6 + dy * 2:.1f} 200,{40 + dy:.1f} C214,{74 - dy * 2:.1f} 250,{70 - dy * 2:.1f} 228,{44 + dy:.1f}"
        for d in (left, right, loop_l, loop_r):
            cords.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="5.4" stroke-linecap="round"/>'
                         f'<path d="{d}" fill="none" stroke="{c}" stroke-width="3.4" stroke-linecap="round"/>')
    return svg(400, 80, "".join(cords))


def seigaiha():
    """A seigaiha tile: wave scales in rows, each over the one behind, ringed in gold — repeats every 40 x 20."""
    rings = []
    # rows from the back to the front: each later circle covers what is under it
    for row, (cy, xs) in enumerate(((0, (0, 40)), (10, (20,)), (20, (0, 40)), (30, (20,)))):
        for cx in xs:
            rings.append(f'<circle cx="{cx}" cy="{cy}" r="20" fill="#120807"/>')
            rings.extend(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GOLD}" stroke-width="1.1"/>' for r in (19, 14.5, 10, 5.5))
    return svg(40, 20, f'<g>{"".join(rings)}</g>')


def asanoha():
    """An asanoha (hemp leaf) tile in silver lines — six-pointed stars of lines, repeats every 30 x 52."""
    w, h = 30, 52
    lines = []
    for cx, cy in ((0, 0), (30, 0), (15, 26), (0, 52), (30, 52)):
        for k in range(6):
            a = math.pi / 6 + k * math.pi / 3
            lines.append(f"M{cx},{cy} L{cx + math.cos(a) * 17.32:.2f},{cy + math.sin(a) * 17.32:.2f}")
        for k in range(6):
            a = k * math.pi / 3
            lines.append(f"M{cx},{cy} L{cx + math.cos(a) * 10:.2f},{cy + math.sin(a) * 10:.2f}")
    lines += [f"M0,0 L{w},0", f"M0,{h} L{w},{h}", f"M0,0 L15,26 L0,52", f"M30,0 L15,26 L30,52"]
    return svg(w, h, f'<path d="{" ".join(lines)}" fill="none" stroke="{SILVER}" stroke-opacity="0.55" stroke-width="0.8"/>')


def kintsugi():
    """Gold seams across a card's lacquered rim: cracks branching in from its edges, mended in gold."""
    rng = random.Random(12)
    w, h = 320, 444
    seams = []
    for sx, sy, a in ((0, 70, 0.3), (320, 150, math.pi - 0.2), (0, 330, -0.25), (320, 390, math.pi + 0.3), (110, 0, 1.3), (230, 444, -1.8)):
        todo = [(sx, sy, a, rng.uniform(90, 170))]
        while todo and len(seams) < 30:
            x, y, ang, left = todo.pop()
            pts = [(x, y)]
            while left > 0:
                step = rng.uniform(5, 13)
                ang += rng.uniform(-0.6, 0.6)
                x, y, left = x + math.cos(ang) * step, y + math.sin(ang) * step, left - step
                pts.append((x, y))
                if rng.random() < 0.1 and left > 30:
                    todo.append((x, y, ang + rng.choice((-1, 1)) * rng.uniform(0.6, 1.1), left * rng.uniform(0.3, 0.6)))
            seams.append("M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts))
    d = " ".join(seams)
    return svg(w, h, f'<path d="{d}" fill="none" stroke="{GOLD_DARK}" stroke-width="3.4" stroke-linejoin="round" stroke-linecap="round"/>'
                     f'<path d="{d}" fill="none" stroke="{GOLD}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
                     f'<path d="{d}" fill="none" stroke="{GOLD_LIGHT}" stroke-width="0.7" stroke-linejoin="round" stroke-linecap="round"/>')


def petal_points(x, y, l, w, turn, squash=1.0):
    pts = []
    for i in range(11):
        t = i / 10
        pts.append((l * 0.9 * t, -w * 0.5 * math.sin(math.pi * (0.08 + t * 0.7)) ** 0.8))
    pts += [(l * 0.97, -w * 0.28), (l * 0.82, 0), (l * 0.97, w * 0.28)]
    for i in range(10, -1, -1):
        t = i / 10
        pts.append((l * 0.9 * t, w * 0.5 * math.sin(math.pi * (0.08 + t * 0.7)) ** 0.8))
    c, s = math.cos(turn), math.sin(turn)
    return [(x + px * c - py * squash * s, y + px * s + py * squash * c) for px, py in pts]


def blossom(x, y, r, turn, fill=SAKURA, heart=GOLD_LIGHT):
    out = []
    for k in range(5):
        out.append(f'<path d="{path(petal_points(x, y, r, r * 0.8, turn + k * math.tau / 5))}" fill="{fill}" stroke="{INK}" stroke-width="{r * 0.06:.1f}"/>')
        out.append(f'<path d="{path(petal_points(x, y, r * 0.4, r * 0.3, turn + k * math.tau / 5))}" fill="{SAKURA_DARK}"/>')
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.17:.1f}" fill="{heart}"/>')
    return "".join(out)


def sakura():
    """Cherry blossoms and petals in a card's corners, over vermillion lacquer."""
    rng = random.Random(21)
    w, h = 320, 444
    body = [blossom(30, 34, 30, 0.2), blossom(76, 14, 17, 1.0), blossom(290, 412, 30, 0.7), blossom(246, 432, 18, 1.4), blossom(298, 360, 13, 0.4)]
    for _ in range(14):
        corner = rng.random() < 0.5
        x = rng.uniform(0, 140) if corner else rng.uniform(180, 320)
        y = rng.uniform(0, 120) if corner else rng.uniform(320, 444)
        body.append(f'<path d="{path(petal_points(x, y, rng.uniform(9, 15), rng.uniform(7, 11), rng.uniform(0, 6), rng.uniform(0.3, 1)))}" fill="{SAKURA}" stroke="{INK}" stroke-width="0.7"/>')
    return svg(w, h, "".join(body))


def drift():
    """Loose cherry petals scattered over a card, to drift across it."""
    rng = random.Random(33)
    body = []
    for _ in range(26):
        x, y = rng.uniform(10, 310), rng.uniform(10, 434)
        body.append(f'<path d="{path(petal_points(x, y, rng.uniform(10, 17), rng.uniform(8, 12), rng.uniform(0, 6), rng.uniform(0.3, 1)))}" fill="{SAKURA}" stroke="{SAKURA_DARK}" stroke-width="0.8"/>')
    return svg(320, 444, "".join(body))


def flecks(seed, count, w=320, h=444):
    """Kirikane: cut gold leaf — little torn squares and slivers scattered."""
    rng = random.Random(seed)
    body = []
    for _ in range(count):
        x, y, s, a = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(1.5, 6), rng.uniform(0, math.pi)
        pts = [(x + math.cos(a + k * math.tau / 4 + rng.uniform(-0.3, 0.3)) * s * rng.uniform(0.6, 1), y + math.sin(a + k * math.tau / 4 + rng.uniform(-0.3, 0.3)) * s * rng.uniform(0.6, 1)) for k in range(4)]
        body.append(f'<path d="{path(pts)}" fill="{rng.choice((GOLD, GOLD_LIGHT, GOLD))}"/>')
    return svg(w, h, "".join(body))


def glint():
    """A gold glint: four long points, a small cross between them."""
    def star(r, k):
        pts = []
        for i in range(64):
            a = i / 64 * math.tau
            c, s = math.cos(a), math.sin(a)
            m = (abs(c) ** k + abs(s) ** k) ** (-1 / k * 2)
            pts.append((50 + c * r * m, 50 + s * r * m))
        return path(pts)
    return svg(100, 100, f'<path d="{star(48, 0.45)}" fill="{GOLD_LIGHT}"/><path d="{star(26, 0.5)}" fill="#ffffff" transform="rotate(45 50 50)"/>')


def seal():
    """A vermillion seal (hanko): a rounded square, its border worn, a white blossom crest in it."""
    rng = random.Random(8)
    edge = []
    for i in range(48):
        u = i / 48
        side = int(u * 4)
        t = u * 4 - side
        x, y = [(8 + 84 * t, 8), (92, 8 + 84 * t), (92 - 84 * t, 92), (8, 92 - 84 * t)][side]
        edge.append((x + rng.uniform(-1.4, 1.4), y + rng.uniform(-1.4, 1.4)))
    crest = blossom(50, 50, 27, -math.pi / 2, fill=WHITE, heart=SHU).replace(INK, SHU_DARK).replace(SAKURA_DARK, "#f3c9c0")
    return svg(100, 100, f'<path d="{path(edge)}" fill="{SHU}"/>{crest}')


TARGETS = {
    "washi.svg": (washi, ("look-sumi", "face-common", "face-rare", "face-epic", "face-legendary")),
    "band.svg": (band, ("look-sumi",)),
    "mizuhiki.svg": (mizuhiki, ("look-sumi",)),
    "enso-gold.svg": (lambda: enso(GOLD, GOLD_DARK, 31), ("look-sumi", "back-sumi")),
    "enso-faint.svg": (lambda: enso(GOLD, GOLD_DARK, 31, 0.32), ("look-sumi",)),
    "seigaiha.svg": (seigaiha, ("back-sumi",)),
    "asanoha.svg": (asanoha, ("face-rare",)),
    "kintsugi.svg": (kintsugi, ("face-legendary",)),
    "sakura.svg": (sakura, ("face-epic",)),
    "petals.svg": (drift, ("face-epic",)),
    "flecks.svg": (lambda: flecks(5, 70), ("look-sumi", "face-legendary")),
    "glint.svg": (glint, ("look-sumi",)),
    "seal.svg": (seal, ("back-sumi",)),
}

if __name__ == "__main__":
    root = Path(sys.argv[1])
    for name, (draw, elements) in TARGETS.items():
        text = draw()
        for element in elements:
            (root / element).mkdir(parents=True, exist_ok=True)
            (root / element / name).write_text(text)
    print("svgs written")
