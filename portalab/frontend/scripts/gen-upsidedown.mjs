#!/usr/bin/env node
/**
 * 027 — draws the Upside Down's shapes and writes them as CSS custom properties
 * (src/design-system/themes/upsidedown.css): red lightning that stays — a thick trunk zigzagging into
 * forks that split at sharp angles and thin to nothing, a pale hot core inside a red body and a soft halo —
 * and the spores and ash that float in that world. Static images, no filter and no animation inside (they
 * would be repainted every frame): the CSS only flickers their opacity. Deterministic (seeded), so the
 * output only changes when this file does. Run: node scripts/gen-upsidedown.mjs
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "../src/design-system/themes/upsidedown.css");

function seeded(seed) {
  let s = seed % 2147483647;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/**
 * One bolt: straight strokes zigzagging around a heading that drifts slowly, thinning as it goes, forking
 * at sharp angles now and then (each fork a thinner, shorter bolt).
 */
function grow(segments, r, { x, y, angle, width: given, length, depth, step, fork = 2.2, main = true }) {
  const steps = Math.max(3, Math.round(length / step));
  // some trunks and branches come out thicker
  const width = given * (r() < 0.35 ? 1.7 : 1);
  let heading = angle;
  let w = width;
  let previous = null;
  for (let i = 0; i < steps; i += 1) {
    heading += (r() - 0.5) * 0.18;
    const a = heading + (r() - 0.5) * 1.15;
    const l = step * (0.6 + r() * 0.8);
    const nx = x + Math.cos(a) * l;
    const ny = y + Math.sin(a) * l;
    const next = width * (1 - ((i + 1) / steps) ** 0.7 * 0.92);
    segments.push(stroke(r, previous, x, y, nx, ny, (w + next) / 2, main));
    previous = [x, y];
    if (depth > 0 && i > 0 && i < steps - 2 && r() < fork / steps) {
      const side = r() < 0.5 ? -1 : 1;
      grow(segments, r, {
        x: nx,
        y: ny,
        angle: heading + side * (0.5 + r() * 0.55),
        width: next * (0.45 + r() * 0.2),
        length: length * (0.3 + r() * 0.3),
        depth: depth - 1,
        step,
        fork,
        main: false,
      });
    }
    x = nx;
    y = ny;
    w = next;
  }
}

const round = (n) => Math.round(n * 10) / 10;

/**
 * A stroke from (x1, y1) to (x2, y2), sometimes bent: the curve leaves the joint along the previous
 * stroke's direction before turning, so that joint is rounded (organic) instead of a sharp angle.
 */
function stroke(r, previous, x1, y1, x2, y2, width, main, chance = 0.4) {
  if (previous && r() < chance) {
    const [px, py] = previous;
    return [x1, y1, x2, y2, width, main, x1 + (x1 - px) * 0.55, y1 + (y1 - py) * 0.55];
  }
  return [x1, y1, x2, y2, width, main];
}

/**
 * A rift across the screen (in a 100 × 100 box stretched to it): a trunk zigzagging down from the top, short
 * branches breaking off sideways and down, thinning as they go.
 */
function rift(r, x0, thickness = 1) {
  const segments = [];
  let x = x0;
  let y = -1;
  const steps = 18 + Math.floor(r() * 8);
  let previous = null;
  for (let i = 0; i < steps; i += 1) {
    const nx = x + (r() - 0.5) * 7;
    const ny = y + 3.5 + r() * 3;
    segments.push(stroke(r, previous, x, y, nx, ny, (5 - (i / steps) * 3) * 0.22 * thickness, true));
    previous = [x, y];
    if (i > 1 && r() > 0.45) {
      const side = r() > 0.5 ? 1 : -1;
      let bx = nx;
      let by = ny;
      let before = [x, y];
      const length = 2 + Math.floor(r() * 5);
      const thick = thickness * (r() < 0.3 ? 1.6 : 1);
      for (let j = 0; j < length; j += 1) {
        const bnx = bx + side * (1.5 + r() * 4.5);
        const bny = by + 1.5 + r() * 3;
        segments.push(stroke(r, before, bx, by, bnx, bny, (3 - (j / length) * 2) * 0.22 * thick, false));
        before = [bx, by];
        bx = bnx;
        by = bny;
      }
    }
    x = nx;
    y = ny;
  }
  return segments;
}

/**
 * Bolts or rifts as an SVG: segments grouped by width and kind (one path each, reused), drawn in three
 * layers — a blurred deep-red halo (the trunks), a red glow, a hot core (pale on the trunks, red on the
 * branches). The image is static, so the browser paints it (blur included) once, not every frame.
 */
function veins({
  w,
  h,
  roots = [],
  segments: given,
  seed = 1,
  step = 9,
  precision = false,
  stretch = false,
  blur = 3,
}) {
  const r = seeded(seed);
  const segments = given ?? [];
  for (const root of roots) grow(segments, r, { step, ...root });
  // segments of one width and kind that follow each other become one path (M x y L x y Q cx cy x y…)
  const buckets = new Map();
  const ends = new Map();
  const p = (n) => (precision ? round(n) : Math.round(n));
  for (const [x1, y1, x2, y2, width, main, cx, cy] of segments) {
    const key = `${main ? "m" : "b"}${Math.max(0.5, Math.round(width * 2) / 2)}`;
    const d = buckets.get(key) ?? [];
    const start = `${p(x1)} ${p(y1)}`;
    const to = cx === undefined ? `L${p(x2)} ${p(y2)}` : `Q${p(cx)} ${p(cy)} ${p(x2)} ${p(y2)}`;
    d.push(ends.get(key) === start ? to : `M${start}${to}`);
    ends.set(key, `${p(x2)} ${p(y2)}`);
    buckets.set(key, d);
  }
  const keys = [...buckets.keys()];
  const defs = keys
    .map((k, i) => `<path id='v${i}' d='${buckets.get(k).join("").replaceAll(" -", "-")}'/>`)
    .join("");
  const layer = (kind, factor) =>
    keys
      .map((k, i) =>
        k[0] === kind || kind === "*"
          ? `<use href='%23v${i}' stroke-width='${round(Number(k.slice(1)) * factor)}'/>`
          : "",
      )
      .join("");
  return [
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${w} ${h}' preserveAspectRatio='${stretch ? "none" : "xMidYMid slice"}'>`,
    `<defs>${defs}<filter id='g' filterUnits='userSpaceOnUse' x='-${w / 10}' y='-${h / 10}' width='${w * 1.2}' height='${h * 1.2}'><feGaussianBlur stdDeviation='${blur}'/></filter></defs>`,
    "<g fill='none' stroke-linecap='round' stroke-linejoin='round'>",
    `<g stroke='%23c80000' stroke-opacity='.3' filter='url(%23g)'>${layer("m", 3)}</g>`,
    `<g stroke='%23dc1414' stroke-opacity='.3'>${layer("m", 1.5)}</g>`,
    `<g stroke='%23c8281e' stroke-opacity='.2'>${layer("b", 1.5)}</g>`,
    `<g stroke='%23ffb4a0' stroke-opacity='.85'>${layer("m", 0.4)}</g>`,
    `<g stroke='%23ff503c' stroke-opacity='.5'>${layer("b", 0.4)}</g>`,
    "</g></svg>",
  ].join("");
}

/** A spore: a soft glowing heart and fine filaments with beaded tips, like a dandelion seed head. */
function spore() {
  const r = seeded(11);
  let filaments = "";
  for (let i = 0; i < 14; i += 1) {
    const a = (i / 14) * Math.PI * 2 + (r() - 0.5) * 0.4;
    const l = 6 + r() * 3.2;
    const x = round(Math.cos(a) * l);
    const y = round(Math.sin(a) * l);
    const cx = round(Math.cos(a + 0.25) * l * 0.5);
    const cy = round(Math.sin(a + 0.25) * l * 0.5);
    filaments += `<path d='M0 0Q${cx} ${cy} ${x} ${y}'/><circle cx='${x}' cy='${y}' r='${round(0.5 + r() * 0.5)}'/>`;
  }
  return [
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='-10 -10 20 20'>",
    "<defs><radialGradient id='c'><stop offset='0' stop-color='%23ffffff'/><stop offset='.45' stop-color='%23e2e8f0' stop-opacity='.8'/><stop offset='1' stop-color='%23e2e8f0' stop-opacity='0'/></radialGradient></defs>",
    `<g stroke='%23e2e8f0' stroke-width='.28' stroke-opacity='.75' fill='%23f1f5f9' fill-opacity='.85'>${filaments}</g>`,
    "<circle r='2.6' fill='url(%23c)'/>",
    "</svg>",
  ].join("");
}

/** Ash: a torn, curled flake, lighter at one edge. */
function flake(seed) {
  const r = seeded(seed);
  const points = [];
  const n = 5 + Math.floor(r() * 3);
  for (let i = 0; i < n; i += 1) {
    const a = (i / n) * Math.PI * 2 + (r() - 0.5) * 0.6;
    const l = 2.5 + r() * 7;
    points.push(`${round(Math.cos(a) * l)} ${round(Math.sin(a) * l * 0.45)}`);
  }
  return [
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='-10 -10 20 20'>",
    "<defs><linearGradient id='a' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%23f1f5f9'/><stop offset='.6' stop-color='%2394a3b8'/><stop offset='1' stop-color='%23334155'/></linearGradient></defs>",
    `<path d='M${points.join("L")}Z' fill='url(%23a)'/>`,
    "</svg>",
  ].join("");
}

const url = (svg) => `url("data:image/svg+xml,${svg.replaceAll("<", "%3C").replaceAll(">", "%3E")}")`;

/**
 * A rift down the screen, drawn in the middle of a box twice as wide (200 × 100, stretched to twice the
 * screen's width) so its branches never end at an edge when it moves left or right.
 */
const screenRift = (seed, x0, thickness) =>
  veins({
    w: 100,
    h: 100,
    segments: rift(seeded(seed), x0, thickness),
    precision: true,
    stretch: true,
    blur: 0.9,
  });
/** Bolts striking in from a screen's left edge (the right one is the mirror of another seed). */
const edge = (seed) =>
  veins({
    w: 700,
    h: 1000,
    seed,
    step: 22,
    blur: 7,
    roots: [
      { x: -5, y: 120, angle: 0.25, width: 9.0, length: 520, depth: 4 },
      { x: -5, y: 520, angle: -0.1, width: 12.0, length: 640, depth: 4 },
      { x: -5, y: 860, angle: -0.45, width: 8.4, length: 470, depth: 3 },
      { x: 120, y: 1005, angle: -1.3, width: 6.6, length: 420, depth: 3 },
    ],
  });
/** A dense web for small round or square things (an avatar ring, a badge). */
const web = () =>
  veins({
    w: 240,
    h: 240,
    seed: 23,
    precision: true,
    step: 11,
    roots: [
      { x: -3, y: 60, angle: 0.3, width: 5.3, length: 220, depth: 3, fork: 3 },
      { x: 243, y: 170, angle: Math.PI - 0.2, width: 5.3, length: 210, depth: 3, fork: 3 },
      { x: 80, y: 243, angle: -1.4, width: 4.6, length: 200, depth: 3, fork: 3 },
      { x: 190, y: -3, angle: 1.9, width: 4.3, length: 190, depth: 3, fork: 3 },
      { x: -3, y: 200, angle: -0.6, width: 3.3, length: 120, depth: 2, fork: 3 },
      { x: 243, y: 30, angle: Math.PI + 0.5, width: 3.3, length: 120, depth: 2, fork: 3 },
    ],
  });
/** A wide strip, the veins at its ends and along its lower edge (a notification, a card, a banner). */
const strip = () =>
  veins({
    w: 640,
    h: 160,
    seed: 41,
    precision: true,
    step: 13,
    roots: [
      { x: -4, y: 40, angle: 0.15, width: 6.3, length: 220, depth: 3 },
      { x: -4, y: 130, angle: -0.35, width: 5.2, length: 170, depth: 3 },
      { x: 644, y: 120, angle: Math.PI + 0.3, width: 6.3, length: 230, depth: 3 },
      { x: 360, y: 164, angle: -1.9, width: 3.1, length: 90, depth: 2 },
      { x: 520, y: -4, angle: 2.2, width: 2.8, length: 80, depth: 2 },
    ],
  });

const css = `/*
 * 027 — the Upside Down's shapes, GENERATED by scripts/gen-upsidedown.mjs (edit that, not this): red
 * lightning that stays (a zigzag trunk forking into thin tips, a pale hot core in a red body, a faint
 * halo) and the spores and ash that float there. Static images; the CSS only flickers their opacity.
 */
:root {
  --veins-rift-a: ${url(screenRift(5, 50, 1.3))};
  --veins-rift-b: ${url(screenRift(13, 50, 1))};
  --veins-rift-c: ${url(screenRift(21, 50, 1.3))};
  --veins-rift-d: ${url(screenRift(29, 50, 0.9))};
  --veins-edge-a: ${url(edge(7))};
  --veins-edge-b: ${url(edge(19))};
  --veins-web: ${url(web())};
  --veins-strip: ${url(strip())};
  --upside-spore: ${url(spore())};
  --upside-flake-a: ${url(flake(3))};
  --upside-flake-b: ${url(flake(8))};
  --upside-flake-c: ${url(flake(15))};
}
`;
writeFileSync(OUT, css);
console.log(`wrote ${OUT} (${Math.round(css.length / 1024)} KiB)`);
