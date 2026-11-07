import { frameInterval, stillFor } from "../../motion/budget";
import { makeNoise } from "./noise";

/**
 * #68: a moving mesh network — a wireframe landscape seen in perspective, its relief rising and falling
 * as it flows toward the viewer, its nodes glowing; it fades into the distance. A grid of a few thousand
 * vertices whose heights come from an evolving noise each frame, drawn as GPU lines and points.
 */
const COLS = 64;
const ROWS = 44;

const VERTEX = `attribute vec3 a_world;
uniform vec2 u_res;
uniform float u_dpr;
varying float v_fade;
varying float v_height;
void main() {
  float focal = 1.15;
  float camY = 0.62;
  float z = a_world.z;
  float aspect = u_res.x / u_res.y;
  vec2 screen = vec2(a_world.x / z * focal / aspect, (a_world.y - camY) / z * focal + 0.18);
  gl_Position = vec4(screen, 0.0, 1.0);
  gl_PointSize = (2.6 / z + 0.6) * u_dpr;
  v_fade = smoothstep(7.5, 2.0, z) * smoothstep(0.25, 0.6, z);
  v_height = a_world.y;
}`;

const FRAGMENT = `precision mediump float;
uniform float u_points;
varying float v_fade;
varying float v_height;
void main() {
  vec3 low = vec3(0.25, 0.45, 1.0);
  vec3 high = vec3(0.85, 0.35, 1.0);
  vec3 col = mix(low, high, clamp(v_height * 2.2 + 0.5, 0.0, 1.0));
  float a = v_fade * 0.55;
  if (u_points > 0.5) {
    float d = length(gl_PointCoord - 0.5);
    a = v_fade * smoothstep(0.5, 0.05, d);
    col = mix(col, vec3(0.9, 0.95, 1.0), 0.5);
  }
  gl_FragColor = vec4(col * a, a);
}`;

export function runMesh(canvas: HTMLCanvasElement): (() => void) | null {
  const gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: true });
  if (!gl) return null;
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
  if (!gl.getProgramParameter(linked, gl.LINK_STATUS)) return null;
  // biome-ignore lint/correctness/useHookAtTopLevel: WebGL's useProgram, not a React hook
  gl.useProgram(linked);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

  const { noise3 } = makeNoise(7);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const world = new Float32Array(COLS * ROWS * 3);
  const indices: number[] = [];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const i = r * COLS + c;
      if (c + 1 < COLS) indices.push(i, i + 1);
      if (r + 1 < ROWS) indices.push(i, i + COLS);
    }
  }
  const worldBuffer = gl.createBuffer();
  const indexBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);
  const aWorld = gl.getAttribLocation(linked, "a_world");
  const uRes = gl.getUniformLocation(linked, "u_res");
  const uPoints = gl.getUniformLocation(linked, "u_points");
  gl.uniform1f(gl.getUniformLocation(linked, "u_dpr"), dpr);

  let frame = 0;
  let last = 0;
  const started = performance.now();
  let held = false;
  const step = (now: number) => {
    frame = requestAnimationFrame(step);
    if (document.hidden || now - last < frameInterval() - 2) return;
    if (held && stillFor(canvas)) return; // #29: one still frame
    last = now;
    held = stillFor(canvas);
    const w = Math.round(canvas.clientWidth * dpr);
    const h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
      gl.viewport(0, 0, w, h);
    }
    const t = (now - started) / 1000;
    const travel = t * 0.45; // the ground flows toward the viewer
    for (let r = 0; r < ROWS; r++) {
      const z = 0.3 + (r / (ROWS - 1)) * 7.5;
      for (let c = 0; c < COLS; c++) {
        const x = (c / (COLS - 1) - 0.5) * 9;
        const n1 = noise3(x * 0.32, (z + travel) * 0.32, t * 0.06);
        const n2 = noise3(x * 0.9, (z + travel) * 0.9, t * 0.11 + 5);
        const i = (r * COLS + c) * 3;
        world[i] = x;
        world[i + 1] = n1 * 0.42 + n2 * 0.12;
        world[i + 2] = z;
      }
    }
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(uRes, w, h);
    gl.bindBuffer(gl.ARRAY_BUFFER, worldBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, world, gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(aWorld);
    gl.vertexAttribPointer(aWorld, 3, gl.FLOAT, false, 0, 0);
    gl.uniform1f(uPoints, 0);
    gl.drawElements(gl.LINES, indices.length, gl.UNSIGNED_SHORT, 0);
    gl.uniform1f(uPoints, 1);
    gl.drawArrays(gl.POINTS, 0, COLS * ROWS);
  };
  frame = requestAnimationFrame(step);
  return () => {
    cancelAnimationFrame(frame);
    gl.deleteBuffer(worldBuffer);
    gl.deleteBuffer(indexBuffer);
    gl.deleteProgram(linked);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  };
}
