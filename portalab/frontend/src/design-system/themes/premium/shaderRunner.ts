/**
 * #68: a full-screen fragment shader drawn on a canvas, made to stay light — drawn at the screen's
 * resolution (lowered on its own when the device struggles), at 30 frames a second at most, the resolution lowered on its
 * own when frames come late, and nothing at all while the tab is hidden. Returns ``null`` when WebGL is not
 * there (the caller falls back to the CSS ambience) and a ``stop`` function otherwise.
 */

const VERTEX = `attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }`;

const FRAME_MS = 1000 / 30;
// of the device pixels (density capped at 1.5): sharp by default, lowered while frames come late
const SCALES = [1, 0.8, 0.62, 0.48, 0.36];
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

export function runShader(canvas: HTMLCanvasElement, fragment: string): (() => void) | null {
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

  let level = 0;
  let late = 0;
  let frames = 0;
  let frame = 0;
  let last = 0;
  const started = performance.now();
  const size = () => {
    const scale = (SCALES[level] ?? 0.36) * DENSITY;
    const width = Math.max(1, Math.round(canvas.clientWidth * scale));
    const height = Math.max(1, Math.round(canvas.clientHeight * scale));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }
  };
  const draw = (now: number) => {
    frame = requestAnimationFrame(draw);
    if (document.hidden) return;
    const gap = now - last;
    if (gap < FRAME_MS - 2) return; // 30 frames a second at most
    last = now;
    // a frame much later than asked, often: the device is struggling — fewer pixels
    frames += 1;
    if (gap > FRAME_MS * 1.6 && gap < 1000) late += 1;
    if (frames >= 60) {
      if (late > 20 && level < SCALES.length - 1) level += 1;
      frames = 0;
      late = 0;
    }
    size();
    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform1f(uTime, ((now - started) / 1000) % 3600);
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
