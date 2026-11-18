/**
 * #68: a full-screen fragment shader drawn on a canvas, made to stay light — drawn at the screen's
 * resolution, at 30 frames a second at most; when frames come late, fewer frames first, then a little
 * resolution (``STEPS``); nothing at all while the tab is hidden. Returns ``null`` when WebGL is not
 * there (the caller falls back to the CSS ambience) and a ``stop`` function otherwise. ``uniforms`` (#88), when
 * given, is asked each frame for the scene's own numbers (``u_<name>``).
 */

export type Uniforms = () => Readonly<Record<string, number>>;

import { frameInterval, stillFor } from "../../motion/budget";

const VERTEX = `attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }`;

/**
 * What a struggling device gives up, step by step while frames come late (issue 506): first the frames — an
 * ambience drifts slowly, fewer frames hardly show — then a little sharpness, never below 62 % of the
 * device pixels (0.36 before: a blurred picture on older phones); still behind at the last step, the CSS
 * ambience stands in. ``scale``: of the device pixels (density capped at 1.5); ``fps``: frames a second
 * at most (the motion budget's own cap still holds).
 */
export const STEPS: ReadonlyArray<{ scale: number; fps: number }> = [
  { scale: 1, fps: 30 },
  { scale: 1, fps: 20 },
  { scale: 1, fps: 15 },
  { scale: 0.8, fps: 15 },
  { scale: 0.62, fps: 12 },
];
const LAST = STEPS[STEPS.length - 1] as { scale: number; fps: number };
const DENSITY = Math.min(typeof window === "undefined" ? 1 : window.devicePixelRatio || 1, 1.5);

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.warn("ambient shader:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

export function runShader(
  canvas: HTMLCanvasElement,
  fragment: string,
  uniforms?: Uniforms,
  /** issue 1: an imported pack's shader — stopped (the CSS ambience instead) if it keeps the device behind */
  guarded = false,
): (() => void) | null {
  const gl = canvas.getContext("webgl", {
    alpha: true,
    premultipliedAlpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    powerPreference: "low-power",
  });
  if (!gl) return null;
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX);
  const pixels = compile(gl, gl.FRAGMENT_SHADER, fragment);
  if (!vertex || !pixels) return null;
  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vertex);
  gl.attachShader(program, pixels);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
  // biome-ignore lint/correctness/useHookAtTopLevel: WebGL's useProgram, not a React hook
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW); // one triangle
  const position = gl.getAttribLocation(program, "a_pos");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  const uResolution = gl.getUniformLocation(program, "u_res");
  const uTime = gl.getUniformLocation(program, "u_time");
  const located = new Map<string, WebGLUniformLocation | null>();
  const where = (name: string) => {
    if (!located.has(name)) located.set(name, gl.getUniformLocation(program, `u_${name}`));
    return located.get(name) ?? null;
  };

  let level = 0;
  let late = 0;
  let frames = 0;
  let frame = 0;
  let last = 0;
  const started = performance.now();
  const size = () => {
    const scale = (STEPS[level] ?? LAST).scale * DENSITY;
    const width = Math.max(1, Math.round(canvas.clientWidth * scale));
    const height = Math.max(1, Math.round(canvas.clientHeight * scale));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }
  };
  let held = false;
  const draw = (now: number) => {
    frame = requestAnimationFrame(draw);
    if (document.hidden) return;
    // #29: half the frames when saving, one still frame when motion is « none »
    if (held && stillFor(canvas)) return;
    const interval = Math.max(frameInterval(), 1000 / (STEPS[level] ?? LAST).fps);
    const gap = now - last;
    if (gap < interval - 2) return; // its step's frames a second at most (30 at best)
    last = now;
    held = stillFor(canvas);
    // a frame much later than asked, often: the device is struggling — fewer pixels
    frames += 1;
    if (gap > interval * 1.6 && gap < 1000) late += 1;
    if (frames >= 60) {
      if (late > 20 && level < STEPS.length - 1) level += 1;
      else if (guarded && late > 30 && level === STEPS.length - 1) {
        // already at its fewest pixels and still far behind: it is given up, the page breathes again
        cancelAnimationFrame(frame);
        canvas.dispatchEvent(new Event("webglcontextlost", { bubbles: true, cancelable: true }));
        return;
      }
      frames = 0;
      late = 0;
    }
    size();
    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform1f(uTime, ((now - started) / 1000) % 3600);
    if (uniforms) for (const [name, value] of Object.entries(uniforms())) gl.uniform1f(where(name), value);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
  frame = requestAnimationFrame(draw);
  return () => {
    cancelAnimationFrame(frame);
    gl.deleteProgram(program);
    gl.deleteShader(vertex);
    gl.deleteShader(pixels);
    gl.deleteBuffer(buffer);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  };
}
