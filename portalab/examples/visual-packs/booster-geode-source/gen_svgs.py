"""Draws the Géode pack's still shapes as SVG — rough stone, a geode's slice, gem-cut facets, veined stone, a cut
gem, glowing cracks, a glint — and writes each into the elements that use it."""

import math
import random
import sys
from pathlib import Path


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'{"<defs>" + defs + "</defs>" if defs else ""}{body}</svg>\n')


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def stone():
    """Rough stone: grey-brown rock in relief, lit from the upper left (turbulence lit as a surface)."""
    defs = ('<filter id="r" x="0" y="0" width="100%" height="100%">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="5" seed="7" result="n"/>'
            '<feDiffuseLighting in="n" lighting-color="#d8cfc8" surfaceScale="6" result="l">'
            '<feDistantLight azimuth="225" elevation="42"/></feDiffuseLighting>'
            '<feColorMatrix in="l" values="0.42 0 0 0 0.02  0 0.36 0 0 0.02  0 0 0.38 0 0.04  0 0 0 0 1"/></filter>')
    return svg(400, 400, '<rect width="400" height="400" filter="url(#r)"/>', defs)


def veins():
    """Polished pale stone: soft lilac-grey veins drifting through it."""
    defs = ('<filter id="v" x="0" y="0" width="100%" height="100%">'
            '<feTurbulence type="turbulence" baseFrequency="0.008 0.02" numOctaves="4" seed="3"/>'
            '<feColorMatrix values="0 0 0 0 0.42  0 0 0 0 0.36  0 0 0 0 0.52  -1.4 0 0 0 0.62"/></filter>')
    return svg(400, 560, '<rect width="400" height="560" filter="url(#v)"/>', defs)


def facets(seed, w=320, h=444, step=40):
    """Gem-cut facets: a jittered grid split into triangles, each a little lighter or darker — laid over a colour."""
    rng = random.Random(seed)
    cols, rows = w // step + 2, h // step + 2
    pts = [[(x * step + rng.uniform(-14, 14) if 0 < x < cols - 1 else x * step,
             y * step + rng.uniform(-14, 14) if 0 < y < rows - 1 else y * step) for x in range(cols)] for y in range(rows)]
    body = []
    for y in range(rows - 1):
        for x in range(cols - 1):
            a, b, c, d = pts[y][x], pts[y][x + 1], pts[y + 1][x], pts[y + 1][x + 1]
            for tri in ((a, b, d), (a, d, c)):
                v = rng.uniform(-1, 1)
                color, alpha = ("#ffffff", v * 0.32) if v > 0 else ("#000000", -v * 0.3)
                body.append(f'<path d="{path(tri)}" fill="{color}" fill-opacity="{alpha:.2f}" stroke="#ffffff" stroke-opacity="0.18" stroke-width="0.6"/>')
    return svg(w, h, "".join(body))


def geode(seed=4):
    """A geode cut in two: its rough rim, bands of agate, a crust of crystal points turned inwards, a deep violet
    heart glinting."""
    rng = random.Random(seed)
    cx = cy = 200

    def blob(r, wobble, n=72):
        ph = [rng.uniform(0, 6) for _ in range(3)]
        return [(cx + math.cos(a) * r * (1 + wobble * (0.6 * math.sin(3 * a + ph[0]) + 0.3 * math.sin(5 * a + ph[1]) + 0.15 * math.sin(9 * a + ph[2]))),
                 cy + math.sin(a) * r * 0.92 * (1 + wobble * (0.6 * math.sin(3 * a + ph[0]) + 0.3 * math.sin(5 * a + ph[1]) + 0.15 * math.sin(9 * a + ph[2]))))
                for a in (i / n * math.tau for i in range(n))]

    body = [f'<path d="{path(blob(190, 0.06))}" fill="#3b302e" stroke="#1a1414" stroke-width="4"/>']
    bands = ["#8a7c86", "#d8d2de", "#6d6584", "#efeaf5", "#9c90b8", "#e3dcef", "#7c6aa8"]
    for i, color in enumerate(bands):
        body.append(f'<path d="{path(blob(172 - i * 9, 0.06))}" fill="{color}"/>')
    inner = blob(108, 0.07, 48)
    body.append(f'<path d="{path(inner)}" fill="#c9b6ec"/>')
    # the crust: points turned inwards, two faces each
    crust = blob(104, 0.07, 40)
    for i, (x, y) in enumerate(crust):
        nx, ny = crust[(i + 1) % len(crust)]
        mx, my = (x + nx) / 2, (y + ny) / 2
        depth = rng.uniform(0.28, 0.5)
        tip = (mx + (cx - mx) * depth, my + (cy - my) * depth)
        body.append(f'<path d="{path([(x, y), tip, (mx, my)])}" fill="#7d43c9"/><path d="{path([(mx, my), tip, (nx, ny)])}" fill="#b98af0"/>')
    body.append(f'<path d="{path(blob(52, 0.12, 36))}" fill="#2a0c4d"/>')
    for _ in range(9):
        x, y, r = cx + rng.uniform(-40, 40), cy + rng.uniform(-30, 30), rng.uniform(2, 5)
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#f3e9ff" fill-opacity="0.8"/>')
    return svg(400, 400, "".join(body))


def gem(colors=("#3d1270", "#7a3cc8", "#b98af0", "#efe2ff")):
    """A cut gem seen from above: an octagon, its table in the middle, facets round it in four tones."""
    dark, mid, light, shine = colors
    outer = [(50 + 46 * math.cos(a), 50 + 46 * math.sin(a)) for a in (math.pi / 8 + i * math.pi / 4 for i in range(8))]
    table = [(50 + 24 * math.cos(a), 50 + 24 * math.sin(a)) for a in (math.pi / 8 + i * math.pi / 4 for i in range(8))]
    tones = [shine, light, mid, dark, dark, mid, light, light]
    body = [f'<path d="{path([outer[i], outer[(i + 1) % 8], table[(i + 1) % 8], table[i]])}" fill="{tones[i]}"/>' for i in range(8)]
    body.append(f'<path d="{path(table)}" fill="{light}"/><path d="{path([table[5], table[6], (50, 50)])}" fill="{shine}" fill-opacity="0.8"/>')
    body.append(f'<path d="{path(outer)}" fill="none" stroke="#120a1e" stroke-width="3"/>')
    return svg(100, 100, "".join(body))


def crust():
    """Amethyst points breaking through the stone at a chipped corner: a fan of crystals, three faces each."""
    rng = random.Random(14)
    body = [f'<path d="{path([(0, 0), (150, 0), (128, 22), (96, 58), (60, 92), (24, 128), (0, 150)])}" fill="#2a0c4d"/>']
    for i in range(11):
        a = math.radians(rng.uniform(8, 82))
        r0, length, w = rng.uniform(0, 30), rng.uniform(50, 110), rng.uniform(16, 26)
        bx, by = r0 * math.cos(a), r0 * math.sin(a)
        ux, uy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)

        def at(x, y):
            return (bx + ux * x + nx * y, by + uy * x + ny * y)

        body_len, mid = length * 0.7, length * 0.82
        faces = [[(0, -w / 2), (body_len, -w / 2), (length, 0), (mid, -w / 6), (0, -w / 6)],
                 [(0, -w / 6), (mid, -w / 6), (length, 0), (mid, w / 6), (0, w / 6)],
                 [(0, w / 6), (mid, w / 6), (length, 0), (body_len, w / 2), (0, w / 2)]]
        for face, color in zip(faces, ("#45137e", "#8a46d8", "#c9a2ff"), strict=True):
            body.append(f'<path d="{path([at(x, y) for x, y in face])}" fill="{color}" stroke="#1c0a33" stroke-width="1"/>')
        tip = at(length, 0)
        body.append(f'<path d="M{at(w * 0.1, w / 6)[0]:.1f},{at(w * 0.1, w / 6)[1]:.1f} L{tip[0]:.1f},{tip[1]:.1f}" stroke="#f4eaff" stroke-width="1.6"/>')
    return svg(160, 160, "".join(body))


def cracks():
    """Cracks of violet light across a pack of stone (they glow while it waits)."""
    rng = random.Random(9)
    lines = []
    for sx, sy, a in ((40, 0, 1.4), (240, 120, 2.6), (0, 300, -0.3), (240, 420, 3.6), (150, 560, -1.6)):
        x, y, pts, left = sx, sy, [(sx, sy)], rng.uniform(120, 200)
        while left > 0:
            a += rng.uniform(-0.6, 0.6)
            step = rng.uniform(8, 16)
            x, y, left = x + math.cos(a) * step, y + math.sin(a) * step, left - step
            pts.append((x, y))
        lines.append("M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts))
    d = " ".join(lines)
    defs = '<filter id="g" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5"/></filter>'
    return svg(240, 560, f'<path d="{d}" fill="none" stroke="#b37bff" stroke-width="10" filter="url(#g)"/>'
                         f'<path d="{d}" fill="none" stroke="#f4eaff" stroke-width="2" stroke-linecap="round"/>', defs)


def glint():
    def star(r, k):
        pts = []
        for i in range(64):
            a = i / 64 * math.tau
            c, s = math.cos(a), math.sin(a)
            m = (abs(c) ** k + abs(s) ** k) ** (-1 / k * 2)
            pts.append((50 + c * r * m, 50 + s * r * m))
        return path(pts)
    defs = '<filter id="b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter>'
    return svg(100, 100, f'<circle cx="50" cy="50" r="16" fill="#c9a2ff" filter="url(#b)"/><path d="{star(48, 0.45)}" fill="#ffffff"/>', defs)


TARGETS = {
    "stone.svg": (stone, ("look-geode", "back-geode", "face-common")),
    "veins.svg": (veins, ("face-common", "face-rare", "face-epic", "face-legendary")),
    "facets.svg": (lambda: facets(5), ("face-rare", "face-epic", "face-legendary", "back-geode")),
    "geode.svg": (geode, ("look-geode", "back-geode")),
    "gem.svg": (gem, ("look-geode",)),
    "cracks.svg": (cracks, ("look-geode",)),
    "crust.svg": (crust, ("look-geode",)),
    "glint.svg": (glint, ("look-geode",)),
}

if __name__ == "__main__":
    root = Path(sys.argv[1])
    for name, (draw, elements) in TARGETS.items():
        text = draw()
        for element in elements:
            (root / element).mkdir(parents=True, exist_ok=True)
            (root / element / name).write_text(text)
    print("svgs written")
