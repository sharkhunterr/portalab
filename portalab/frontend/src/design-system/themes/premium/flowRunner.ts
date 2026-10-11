import { makeNoise } from "./noise";

/**
 * #68: thousands of fine particles carried by a turbulent flow field (the curl of an evolving noise) plus
 * a wind with gusts — they move in masses, swirl, thicken and thin out, never in straight lines. Simulated
 * on the CPU (a few thousand points), drawn by the GPU as soft points; same budget rules as the shaders
 * (30 frames a second, paused while hidden, fewer particles when frames come late).
 */
export interface FlowPreset {
  /** particles per million CSS pixels (scaled to the screen) */
  density: number;
  colors: ReadonlyArray<readonly [number, number, number]>;
  size: readonly [number, number];
  alpha: readonly [number, number];
  /** pixels per second the flow carries them */
  speed: number;
  /** size of the swirls: smaller = bigger eddies */
  scale: number;
  /** how fast the flow itself changes */
  evolve: number;
  /** steady wind in pixels per second, and how strongly gusts swing it (0..1) */
  wind: readonly [number, number];
  gusts: number;
  /** where a particle is born again: anywhere, along the upwind edge, or at the bottom */
  spawn: "anywhere" | "upwind" | "bottom";
  /** seconds a particle lives (fading in and out); 0 = until it leaves */
  life?: readonly [number, number];
  /** a flicker of brightness (embers) */
  flicker?: boolean;
  /** seconds of motion trail drawn behind each particle (its speed made visible); 0 = none */
  streak?: number;
  /** also draw the particle itself as a soft dot (snowflakes, embers) */
  dots?: boolean;
  /** pixels per second the wind swings sideways in gusts (the rain's slant changing) */
  sway?: number;
}

export const FLOWS: Record<string, FlowPreset> = {
  // pale wisps drifting slowly, appearing and fading
  wisps: {
    density: 45,
    colors: [
      [0.75, 0.82, 0.85],
      [0.6, 0.7, 0.72],
    ],
    size: [6, 16],
    alpha: [0.06, 0.2],
    speed: 25,
    scale: 0.0015,
    evolve: 0.06,
    wind: [4, -6],
    gusts: 0.3,
    spawn: "anywhere",
    life: [6, 12],
    dots: true,
  },
  // gentle Christmas snow: big soft flakes, slowly drifting down
  gentlesnow: {
    density: 380,
    colors: [
      [1, 1, 1],
      [0.92, 0.95, 1],
    ],
    size: [1.5, 6],
    alpha: [0.4, 0.95],
    speed: 25,
    scale: 0.002,
    evolve: 0.08,
    wind: [12, 45],
    gusts: 0.4,
    spawn: "upwind",
    dots: true,
  },
  // the hearth's crackle: sparks bursting up, short-lived
  crackle: {
    density: 160,
    colors: [
      [1, 0.65, 0.2],
      [1, 0.85, 0.45],
      [1, 0.45, 0.1],
    ],
    size: [1.2, 3],
    alpha: [0.7, 1],
    speed: 60,
    scale: 0.004,
    evolve: 0.4,
    wind: [0, -150],
    gusts: 0.5,
    spawn: "bottom",
    life: [0.6, 2],
    flicker: true,
    streak: 0.04,
    dots: true,
  },
  // volcanic ash: grey flakes lifted by the heat, swirling up
  ash: {
    density: 700,
    colors: [
      [0.45, 0.42, 0.4],
      [0.3, 0.28, 0.27],
      [0.6, 0.55, 0.5],
    ],
    size: [1, 3.5],
    alpha: [0.25, 0.7],
    speed: 60,
    scale: 0.0025,
    evolve: 0.15,
    wind: [20, -70],
    gusts: 0.4,
    spawn: "bottom",
    life: [4, 9],
    dots: true,
  },
  // embers and ash torn sideways by the wind of a firestorm
  windash: {
    density: 650,
    colors: [
      [1, 0.55, 0.15],
      [1, 0.75, 0.35],
      [0.45, 0.4, 0.38],
      [0.95, 0.35, 0.08],
    ],
    size: [1, 3],
    alpha: [0.45, 1],
    speed: 70,
    scale: 0.002,
    evolve: 0.2,
    wind: [280, -60],
    gusts: 0.6,
    spawn: "upwind",
    streak: 0.05,
    flicker: true,
    dots: true,
  },
  // plankton: specks drifting slowly in the water
  plankton: {
    density: 500,
    colors: [
      [0.7, 0.95, 1],
      [0.5, 0.85, 0.95],
    ],
    size: [0.8, 2.4],
    alpha: [0.2, 0.6],
    speed: 18,
    scale: 0.003,
    evolve: 0.08,
    wind: [6, -4],
    gusts: 0.3,
    spawn: "anywhere",
    dots: true,
  },
  // a school of fish: silver darts moving together, turning with the big eddies
  school: {
    density: 160,
    colors: [
      [0.8, 0.9, 1],
      [0.65, 0.8, 0.95],
    ],
    size: [2, 3.5],
    alpha: [0.55, 0.95],
    speed: 35,
    scale: 0.0007,
    evolve: 0.04,
    wind: [110, -6],
    gusts: 0.3,
    spawn: "upwind",
    streak: 0.09,
    dots: true,
  },
  // night blizzard: dense snow driven hard sideways, in several depths
  nightsnow: {
    density: 1700,
    colors: [
      [1, 1, 1],
      [0.85, 0.9, 1],
    ],
    size: [1, 5.5],
    alpha: [0.3, 0.95],
    speed: 110,
    scale: 0.0016,
    evolve: 0.15,
    wind: [320, 140],
    gusts: 0.7,
    sway: 120,
    spawn: "upwind",
    streak: 0.04,
    dots: true,
  },
  // fireflies: points of light wandering, glowing and fading
  fireflies: {
    density: 90,
    colors: [
      [0.85, 1, 0.45],
      [1, 0.95, 0.5],
    ],
    size: [2.5, 5.5],
    alpha: [0.6, 1],
    speed: 22,
    scale: 0.004,
    evolve: 0.2,
    wind: [0, -3],
    gusts: 0.2,
    spawn: "anywhere",
    life: [3, 8],
    flicker: true,
    dots: true,
  },
  // storm rain: fast thin streaks, their slant swinging with the gusts, ruffled by turbulence
  storm: {
    density: 1500,
    colors: [
      [0.72, 0.8, 0.95],
      [0.62, 0.7, 0.88],
      [0.85, 0.9, 1],
    ],
    size: [1, 2],
    alpha: [0.18, 0.6],
    speed: 70,
    scale: 0.0012,
    evolve: 0.25,
    wind: [120, 950],
    gusts: 0.25,
    sway: 260,
    spawn: "upwind",
    streak: 0.045,
  },
  // sand: dense fine grains moving in masses with the gusts, eddies of all sizes
  sand: {
    density: 2600,
    colors: [
      [0.93, 0.76, 0.5],
      [0.85, 0.62, 0.36],
      [0.98, 0.86, 0.64],
      [0.72, 0.5, 0.28],
    ],
    size: [0.7, 2.1],
    alpha: [0.3, 0.9],
    speed: 160,
    scale: 0.0022,
    evolve: 0.12,
    wind: [260, 12],
    gusts: 0.75,
    spawn: "upwind",
    streak: 0.07,
  },
  // snow: flakes of every size, the near ones big and fast, tumbling in the gusts
  snow: {
    density: 1100,
    colors: [
      [1, 1, 1],
      [0.88, 0.93, 1],
    ],
    size: [1.2, 6.5],
    alpha: [0.35, 0.95],
    speed: 90,
    scale: 0.0018,
    evolve: 0.1,
    wind: [110, 120],
    gusts: 0.65,
    spawn: "upwind",
    streak: 0.035,
    dots: true,
  },
  // embers: sparks born at the bottom, lifted by the heat, swirling, glowing then dying
  embers: {
    density: 420,
    colors: [
      [1, 0.62, 0.18],
      [1, 0.42, 0.08],
      [1, 0.85, 0.45],
    ],
    size: [1.5, 4.5],
    alpha: [0.7, 1],
    speed: 80,
    scale: 0.003,
    evolve: 0.3,
    wind: [8, -120],
    gusts: 0.3,
    spawn: "bottom",
    life: [2, 5.5],
    flicker: true,
    streak: 0.06,
    dots: true,
  },
};

const VERTEX = `attribute vec2 a_pos;
attribute vec4 a_look; // size, alpha, colour index, unused
uniform vec2 u_res;
uniform float u_dpr;
uniform vec3 u_colors[4];
varying float v_alpha;
varying vec3 v_color;
void main() {
  vec2 clip = a_pos / u_res * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
  gl_PointSize = a_look.x * u_dpr;
  v_alpha = a_look.y;
  int i = int(a_look.z);
  v_color = i == 0 ? u_colors[0] : i == 1 ? u_colors[1] : i == 2 ? u_colors[2] : u_colors[3];
}`;

const FRAGMENT = `precision mediump float;
uniform float u_lines;
varying float v_alpha;
varying vec3 v_color;
void main() {
  float a = v_alpha;
  if (u_lines < 0.5) a *= smoothstep(0.5, 0.1, length(gl_PointCoord - 0.5));
  gl_FragColor = vec4(v_color * a, a);
}`;

const FRAME_MS = 1000 / 30;

function program(gl: WebGLRenderingContext): WebGLProgram | null {
  const make = (type: number, source: string) => {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
  };
  const vertex = make(gl.VERTEX_SHADER, VERTEX);
  const fragment = make(gl.FRAGMENT_SHADER, FRAGMENT);
  const linked = gl.createProgram();
  if (!vertex || !fragment || !linked) return null;
  gl.attachShader(linked, vertex);
  gl.attachShader(linked, fragment);
  gl.linkProgram(linked);
  return gl.getProgramParameter(linked, gl.LINK_STATUS) ? linked : null;
}

export function runFlow(canvas: HTMLCanvasElement, preset: FlowPreset): (() => void) | null {
  const gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false });
  if (!gl) return null;
  const linked = program(gl);
  if (!linked) return null;
  // biome-ignore lint/correctness/useHookAtTopLevel: WebGL's useProgram, not a React hook
  gl.useProgram(linked);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  const { curl } = makeNoise(Math.floor(Math.random() * 1e9));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const colors = new Float32Array(12);
  for (let i = 0; i < 4; i++) colors.set(preset.colors[i % preset.colors.length] as readonly number[], i * 3);
  gl.uniform3fv(gl.getUniformLocation(linked, "u_colors"), colors);
  gl.uniform1f(gl.getUniformLocation(linked, "u_dpr"), dpr);
  const uRes = gl.getUniformLocation(linked, "u_res");
  const uLines = gl.getUniformLocation(linked, "u_lines");
  const aPos = gl.getAttribLocation(linked, "a_pos");
  const aLook = gl.getAttribLocation(linked, "a_look");
  const posBuffer = gl.createBuffer();
  const lookBuffer = gl.createBuffer();

  let width = 0;
  let height = 0;
  let count = 0;
  let budget = 1; // share of the particles drawn, lowered when frames come late
  let pos = new Float32Array(0); // x, y per particle
  let look = new Float32Array(0); // size, alpha, colour, unused
  let age = new Float32Array(0);
  let life = new Float32Array(0);
  let base = new Float32Array(0); // each particle's own alpha
  let vel = new Float32Array(0); // x, y velocity per particle (for the trails)
  let trail = new Float32Array(0); // two ends per particle
  let trailLook = new Float32Array(0);
  const flow = new Float32Array(2);
  const rand = (a: number, b: number) => a + Math.random() * (b - a);

  const born = (i: number, initial: boolean) => {
    const [wx, wy] = preset.wind;
    if (initial || preset.spawn === "anywhere") {
      pos[i * 2] = Math.random() * width;
      pos[i * 2 + 1] = Math.random() * height;
    } else if (preset.spawn === "bottom") {
      pos[i * 2] = Math.random() * width;
      pos[i * 2 + 1] = height + rand(0, 30);
    } else if (Math.abs(wx) * width > Math.abs(wy) * height * Math.random() * 2) {
      pos[i * 2] = wx > 0 ? rand(-40, 0) : width + rand(0, 40); // from the side the wind comes from
      pos[i * 2 + 1] = Math.random() * height;
    } else {
      pos[i * 2] = Math.random() * width;
      pos[i * 2 + 1] = wy > 0 ? rand(-40, 0) : height + rand(0, 40);
    }
    const near = Math.random() ** 2.2; // most are small and far, a few near and big
    look[i * 4] = preset.size[0] + near * (preset.size[1] - preset.size[0]);
    base[i] = preset.alpha[0] + near * (preset.alpha[1] - preset.alpha[0]);
    look[i * 4 + 2] = Math.floor(Math.random() * 4);
    age[i] = initial && preset.life ? Math.random() * (preset.life[1] as number) : 0;
    life[i] = preset.life ? rand(preset.life[0], preset.life[1]) : 0;
  };

  const resize = () => {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w === width && h === height) return;
    width = w;
    height = h;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
    count = Math.round((preset.density * w * h) / 1e6);
    pos = new Float32Array(count * 2);
    look = new Float32Array(count * 4);
    age = new Float32Array(count);
    life = new Float32Array(count);
    base = new Float32Array(count);
    vel = new Float32Array(count * 2);
    trail = new Float32Array(count * 4);
    trailLook = new Float32Array(count * 8);
    for (let i = 0; i < count; i++) born(i, true);
  };

  let frame = 0;
  let last = performance.now();
  let late = 0;
  let frames = 0;
  const started = last;
  const step = (now: number) => {
    frame = requestAnimationFrame(step);
    if (document.hidden) {
      last = now;
      return;
    }
    const gap = now - last;
    if (gap < FRAME_MS - 2) return;
    last = now;
    frames += 1;
    if (gap > FRAME_MS * 1.6 && gap < 1000) late += 1;
    if (frames >= 60) {
      if (late > 20) budget = Math.max(0.3, budget * 0.75);
      frames = 0;
      late = 0;
    }
    resize();
    const dt = Math.min(gap, 100) / 1000;
    const t = (now - started) / 1000;
    // gusts: the wind swells and eases on its own rhythm, never quite periodic
    const gust = 1 + preset.gusts * (0.6 * Math.sin(t * 0.37) + 0.4 * Math.sin(t * 1.13 + 1.7));
    const swing = preset.sway
      ? preset.sway *
        (0.7 * Math.sin(t * 0.23 + 0.5) + 0.3 * Math.sin(t * 0.71 + 2.1) + 0.15 * Math.sin(t * 1.9))
      : 0;
    const wx = preset.wind[0] + swing;
    const wy = preset.wind[1];
    const drawn = Math.floor(count * budget);
    for (let i = 0; i < drawn; i++) {
      const x = pos[i * 2] as number;
      const y = pos[i * 2 + 1] as number;
      curl(x * preset.scale, y * preset.scale, t * preset.evolve, flow);
      const near = ((look[i * 4] as number) - preset.size[0]) / (preset.size[1] - preset.size[0] || 1);
      const pace = 0.55 + near * 0.9; // near particles move faster (parallax)
      const vx = ((flow[0] as number) * preset.speed + wx * gust) * pace;
      const vy = ((flow[1] as number) * preset.speed + wy * gust) * pace;
      vel[i * 2] = vx;
      vel[i * 2 + 1] = vy;
      pos[i * 2] = x + vx * dt;
      pos[i * 2 + 1] = y + vy * dt;
      let alpha = base[i] as number;
      if (preset.life) {
        age[i] = (age[i] as number) + dt;
        const k = (age[i] as number) / (life[i] as number);
        alpha *= Math.min(1, k * 6) * (1 - k);
        if (k >= 1) born(i, false);
      }
      if (preset.flicker) alpha *= 0.65 + 0.35 * Math.sin(t * 9 + i);
      look[i * 4 + 1] = alpha;
      const px = pos[i * 2] as number;
      const py = pos[i * 2 + 1] as number;
      if (px < -60 || px > width + 60 || py < -60 || py > height + 60) born(i, false);
    }
    gl.uniform2f(uRes, width, height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (preset.streak) {
      // each particle's trail: from where it is back along its velocity, fading to nothing
      for (let i = 0; i < drawn; i++) {
        const px = pos[i * 2] as number;
        const py = pos[i * 2 + 1] as number;
        trail[i * 4] = px;
        trail[i * 4 + 1] = py;
        trail[i * 4 + 2] = px - (vel[i * 2] as number) * preset.streak;
        trail[i * 4 + 3] = py - (vel[i * 2 + 1] as number) * preset.streak;
        const colour = look[i * 4 + 2] as number;
        trailLook[i * 8] = 1;
        trailLook[i * 8 + 1] = (look[i * 4 + 1] as number) * 0.9;
        trailLook[i * 8 + 2] = colour;
        trailLook[i * 8 + 4] = 1;
        trailLook[i * 8 + 5] = 0;
        trailLook[i * 8 + 6] = colour;
      }
      gl.uniform1f(uLines, 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, trail.subarray(0, drawn * 4), gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(aPos);
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, lookBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, trailLook.subarray(0, drawn * 8), gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(aLook);
      gl.vertexAttribPointer(aLook, 4, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.LINES, 0, drawn * 2);
      if (!preset.dots) return;
    }
    gl.uniform1f(uLines, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, pos.subarray(0, drawn * 2), gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, lookBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, look.subarray(0, drawn * 4), gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(aLook);
    gl.vertexAttribPointer(aLook, 4, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.POINTS, 0, drawn);
  };
  frame = requestAnimationFrame(step);
  return () => {
    cancelAnimationFrame(frame);
    gl.deleteBuffer(posBuffer);
    gl.deleteBuffer(lookBuffer);
    gl.deleteProgram(linked);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  };
}
