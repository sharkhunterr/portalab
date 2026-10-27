import { useEffect, useRef } from "react";

/**
 * Issue 255: the stage's mist for a booster of media cards — its fog banks drifting, its projectors sweeping, its
 * dust rising, as the stage's own CSS layers draw them, but painted on one small canvas (half the screen's size
 * at most, stretched: the fog is soft anyway) about thirty times a second. A phone drawing the cards' foil and HD
 * backdrops tore with a dozen screen-sized layers moving behind them; one small picture changing costs it next to
 * nothing. ``hold`` keeps the last picture while a card turns or has its moment, or one is seen big.
 */
export function StageMist({ hold, reduced }: { hold: boolean; reduced: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const held = useRef(hold);
  held.current = hold;

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext("2d");
    if (!element || !context) {
      if (element) element.dataset.failed = "";
      return;
    }
    const colors = resolve(element);
    const sprites = {
      epic: blob(colors.epic),
      rare: blob(colors.rare),
      light: blob(colors.light),
      mote: blob(colors.light, 16),
      beam: beam(colors.light, colors.epic),
    };
    let width = 0;
    let height = 0;
    let scale = 1;
    const size = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      scale = Math.min(0.5, 640 / Math.max(width, height, 1));
      element.width = Math.max(1, Math.round(width * scale));
      element.height = Math.max(1, Math.round(height * scale));
    };
    size();
    window.addEventListener("resize", size);

    const started = performance.now();
    let frame = 0;
    let last = -Infinity;
    const paint = (time: number) => {
      context.setTransform(1, 0, 0, 1, 0, 0);
      context.clearRect(0, 0, element.width, element.height);
      context.setTransform(scale, 0, 0, scale, 0, 0);
      drawFog(context, sprites, width, height, time);
      drawBeams(context, sprites.beam, width, height, time);
      drawDust(context, sprites.mote, width, height, time);
    };
    const loop = (now: number) => {
      frame = requestAnimationFrame(loop);
      if (held.current || document.hidden || now - last < 32) return;
      last = now;
      paint((now - started) / 1000);
    };
    if (reduced) paint(4);
    else frame = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", size);
    };
  }, [reduced]);

  return <canvas ref={canvas} className="booster-atmosphere__mist" />;
}

type Sprites = Record<"epic" | "rare" | "light" | "mote" | "beam", HTMLCanvasElement>;

/** The stage's colours as its tokens set them (a pack's scene may set its own). */
function resolve(within: HTMLElement) {
  const probe = document.createElement("span");
  within.parentElement?.appendChild(probe);
  const of = (token: string) => {
    probe.style.color = `var(${token})`;
    return getComputedStyle(probe).color;
  };
  const colors = { light: of("--booster-light"), epic: of("--booster-epic"), rare: of("--booster-rare") };
  probe.remove();
  return colors;
}

/** A canvas filled with ``color``, its alpha then cut by what ``shape`` draws (a gradient's alpha only). */
function tinted(color: string, w: number, h: number, shape: (c: CanvasRenderingContext2D) => void) {
  const sprite = document.createElement("canvas");
  sprite.width = w;
  sprite.height = h;
  const c = sprite.getContext("2d");
  if (!c) return sprite;
  c.fillStyle = color;
  c.fillRect(0, 0, w, h);
  c.globalCompositeOperation = "destination-in";
  shape(c);
  return sprite;
}

/** A soft round of light, opaque in its middle, gone at its edge. */
function blob(color: string, side = 64) {
  return tinted(color, side, side, (c) => {
    const r = side / 2;
    const fall = c.createRadialGradient(r, r, 0, r, r, r);
    fall.addColorStop(0, "black");
    fall.addColorStop(1, "transparent");
    c.fillStyle = fall;
    c.fillRect(0, 0, side, side);
  });
}

/** A projector's cone: narrow at the top, its light fading down into the epic's colour, then into nothing. */
function beam(light: string, epic: string) {
  const w = 24;
  const h = 96;
  // only the alpha of what is drawn counts (destination-in): black, faded by ``strength``, then nothing
  const cone = (c: CanvasRenderingContext2D, strength: number, stops: [number, boolean][]) => {
    const down = c.createLinearGradient(0, 0, 0, h);
    for (const [at, lit] of stops) down.addColorStop(at, lit ? "black" : "transparent");
    c.globalAlpha = strength;
    c.fillStyle = down;
    c.beginPath();
    c.moveTo(w * 0.44, 0);
    c.lineTo(w * 0.56, 0);
    c.lineTo(w, h);
    c.lineTo(0, h);
    c.closePath();
    c.fill();
  };
  const top = tinted(light, w, h, (c) =>
    cone(c, 0.16, [
      [0, true],
      [0.55, false],
    ]),
  );
  const low = tinted(epic, w, h, (c) =>
    cone(c, 0.08, [
      [0, false],
      [0.55, true],
      [1, false],
    ]),
  );
  const sprite = document.createElement("canvas");
  sprite.width = w;
  sprite.height = h;
  const c = sprite.getContext("2d");
  c?.drawImage(top, 0, 0);
  c?.drawImage(low, 0, 0);
  return sprite;
}

/** 0 → 1 → 0 over ``period`` seconds, eased (an ``ease-in-out infinite alternate``). */
function swing(time: number, period: number, delay = 0) {
  const phase = ((((time - delay) / period) % 2) + 2) % 2;
  const x = phase > 1 ? 2 - phase : phase;
  return x * x * (3 - 2 * x);
}

// the three banks (booster-drift-a/b/c): each a box 160 % of the screen drifting and growing, its rounds of light
// placed in it (x, y, radii, as fractions of the box; strength in %)
const BANKS = [
  {
    period: 38,
    to: [0.08, -0.06, 0.15],
    rounds: [
      ["epic", 0.2, 0.7, 0.4, 0.3, 40],
      ["rare", 0.8, 0.3, 0.35, 0.25, 30],
    ],
  },
  {
    period: 52,
    to: [-0.1, 0.05, 0.1],
    rounds: [
      ["light", 0.6, 0.85, 0.45, 0.22, 16],
      ["epic", 0.15, 0.2, 0.3, 0.3, 18],
    ],
  },
  { period: 26, to: [0.04, -0.03, 0], rounds: [["light", 0.5, 1, 0.6, 0.18, 22]] },
] as const;

function drawFog(c: CanvasRenderingContext2D, sprites: Sprites, w: number, h: number, time: number) {
  for (const bank of BANKS) {
    const e = swing(time, bank.period);
    const bw = w * 1.6;
    const bh = h * 1.6;
    const grow = 1 + bank.to[2] * e;
    const cx = w / 2 + bank.to[0] * bw * e;
    const cy = h / 2 + bank.to[1] * bh * e;
    for (const [kind, x, y, rx, ry, strength] of bank.rounds) {
      const px = cx + (x - 0.5) * bw * grow;
      const py = cy + (y - 0.5) * bh * grow;
      const sx = rx * bw * grow * 1.6;
      const sy = ry * bh * grow * 1.6;
      c.globalAlpha = Math.min(1, (strength / 100) * 1.6);
      c.drawImage(sprites[kind], px - sx / 2, py - sy / 2, sx, sy);
    }
  }
  c.globalAlpha = 1;
}

// the projectors (booster-sweep): where they hang, how long a swing takes, how far into it they start
const BEAMS = [
  { at: 0.18, period: 9, delay: -3, reverse: false },
  { at: 0.5, period: 13, delay: 0, reverse: true },
  { at: 0.82, period: 10, delay: -6, reverse: false },
];

function drawBeams(
  c: CanvasRenderingContext2D,
  sprite: HTMLCanvasElement,
  w: number,
  h: number,
  time: number,
) {
  const width = Math.max(w, h) * 0.34;
  const top = -0.12 * h;
  const length = 0.97 * h;
  for (const projector of BEAMS) {
    const e = swing(time, projector.period, projector.delay);
    const k = projector.reverse ? 1 - e : e;
    c.save();
    c.translate(projector.at * w, top);
    c.rotate(((-22 + 44 * k) * Math.PI) / 180);
    c.globalAlpha = 0.55 + 0.45 * k;
    c.drawImage(sprite, -width / 2, 0, width, length);
    c.restore();
  }
  c.globalAlpha = 1;
}

// the dust (booster-dust): 34 motes rising from below the stage, each its own column, speed, size and drift
const MOTES = Array.from({ length: 34 }, (_, i) => ({
  x: noise(i, 1),
  delay: -noise(i, 2) * 14,
  duration: 9 + noise(i, 3) * 10,
  size: 1 + noise(i, 4) * 3,
  drift: (noise(i, 5) - 0.5) * 120,
}));

function drawDust(
  c: CanvasRenderingContext2D,
  sprite: HTMLCanvasElement,
  w: number,
  h: number,
  time: number,
) {
  for (const mote of MOTES) {
    const p = ((((time - mote.delay) / mote.duration) % 1) + 1) % 1;
    const alpha =
      p < 0.1 ? (p / 0.1) * 0.55 : p < 0.9 ? 0.55 - ((p - 0.1) / 0.8) * 0.35 : 0.2 * ((1 - p) / 0.1);
    const side = mote.size * 4;
    c.globalAlpha = alpha;
    c.drawImage(
      sprite,
      mote.x * w + mote.drift * p - side / 2,
      h * 1.02 - p * h * 1.05 - side / 2,
      side,
      side,
    );
  }
  c.globalAlpha = 1;
}

function noise(seed: number, n: number): number {
  const x = Math.sin(seed * 9301 + n * 49297 + 233) * 43758.5453;
  return x - Math.floor(x);
}
