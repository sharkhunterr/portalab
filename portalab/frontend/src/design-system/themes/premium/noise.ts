/**
 * #68: 3D simplex noise (the public algorithm by Ken Perlin, written after Stefan Gustavson's description)
 * and its curl — a flow field without sources or sinks: particles following it swirl in coherent masses
 * instead of drifting in straight lines, and the field itself changes with time (the third dimension).
 */

const GRAD = [
  [1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1],
  [1, 0, -1], [-1, 0, -1], [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1],
] as const; // biome-ignore format: the twelve gradients read as a table
const F3 = 1 / 3;
const G3 = 1 / 6;

export function makeNoise(seed = 1) {
  const perm = new Uint8Array(512);
  const p = new Uint8Array(256).map((_, i) => i);
  let s = seed >>> 0 || 1;
  for (let i = 255; i > 0; i--) {
    s = (s * 1664525 + 1013904223) >>> 0;
    const j = s % (i + 1);
    [p[i], p[j]] = [p[j] as number, p[i] as number];
  }
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255] as number;

  const corner = (gi: number, x: number, y: number, z: number) => {
    const t = 0.6 - x * x - y * y - z * z;
    if (t < 0) return 0;
    const g = GRAD[gi % 12] as readonly number[];
    return t * t * t * t * ((g[0] as number) * x + (g[1] as number) * y + (g[2] as number) * z);
  };

  /** Simplex noise in [-1, 1]. */
  function noise3(x: number, y: number, z: number): number {
    const s0 = (x + y + z) * F3;
    const i = Math.floor(x + s0);
    const j = Math.floor(y + s0);
    const k = Math.floor(z + s0);
    const t0 = (i + j + k) * G3;
    const x0 = x - (i - t0);
    const y0 = y - (j - t0);
    const z0 = z - (k - t0);
    let i1: number;
    let j1: number;
    let k1: number;
    let i2: number;
    let j2: number;
    let k2: number;
    if (x0 >= y0) {
      if (y0 >= z0) [i1, j1, k1, i2, j2, k2] = [1, 0, 0, 1, 1, 0];
      else if (x0 >= z0) [i1, j1, k1, i2, j2, k2] = [1, 0, 0, 1, 0, 1];
      else [i1, j1, k1, i2, j2, k2] = [0, 0, 1, 1, 0, 1];
    } else if (y0 < z0) [i1, j1, k1, i2, j2, k2] = [0, 0, 1, 0, 1, 1];
    else if (x0 < z0) [i1, j1, k1, i2, j2, k2] = [0, 1, 0, 0, 1, 1];
    else [i1, j1, k1, i2, j2, k2] = [0, 1, 0, 1, 1, 0];
    const x1 = x0 - i1 + G3;
    const y1 = y0 - j1 + G3;
    const z1 = z0 - k1 + G3;
    const x2 = x0 - i2 + 2 * G3;
    const y2 = y0 - j2 + 2 * G3;
    const z2 = z0 - k2 + 2 * G3;
    const x3 = x0 - 1 + 3 * G3;
    const y3 = y0 - 1 + 3 * G3;
    const z3 = z0 - 1 + 3 * G3;
    const ii = i & 255;
    const jj = j & 255;
    const kk = k & 255;
    const at = (a: number, b: number, c: number) =>
      perm[ii + a + (perm[jj + b + (perm[kk + c] as number)] as number)] as number;
    return (
      32 *
      (corner(at(0, 0, 0), x0, y0, z0) +
        corner(at(i1, j1, k1), x1, y1, z1) +
        corner(at(i2, j2, k2), x2, y2, z2) +
        corner(at(1, 1, 1), x3, y3, z3))
    );
  }

  /** The curl of the noise at (x, y), the field evolving with ``t``: a swirling, divergence-free flow. */
  function curl(x: number, y: number, t: number, out: Float32Array): void {
    const e = 0.01;
    const dy = noise3(x, y + e, t) - noise3(x, y - e, t);
    const dx = noise3(x + e, y, t) - noise3(x - e, y, t);
    out[0] = dy / (2 * e);
    out[1] = -dx / (2 * e);
  }

  return { noise3, curl };
}
