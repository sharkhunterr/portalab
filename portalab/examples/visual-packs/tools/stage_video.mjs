// Makes a scene's backdrop video from its GLSL stage (issue 287): the stage drawn frame by frame in Portalab's
// own shader wrapper (read from the frontend's badgeFx.ts), at 24 frames a second, its last half second blended
// into its first so it loops without a seam, encoded as H.264 (no transparency: a backdrop fills the stage).
// A phone then decodes a video instead of running a full-screen shader every frame.
//   node stage_video.mjs STAGE.glsl OUT.mp4 [--seconds 6] [--width 1920] [--height 1080] [--crf 22]
// Needs the frontend's dependencies (Playwright's Chromium) and ffmpeg.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? Number(args[i + 1]) : fallback;
};
const [stage, out] = args.filter((a, i) => !a.startsWith("--") && !args[i - 1]?.startsWith("--"));
const seconds = option("seconds", 6), width = option("width", 1920), height = option("height", 1080), crf = option("crf", 22);
const fps = 24, blend = 12, count = seconds * fps;
const front = resolve(dirname(fileURLToPath(import.meta.url)), "../../../frontend");
const { chromium } = createRequire(join(front, "package.json"))("@playwright/test");
const wrapper = readFileSync(join(front, "src/design-system/themes/premium/badgeFx.ts"), "utf8");
const literal = (name) => wrapper.match(new RegExp(`const ${name} = \`([\\s\\S]*?)\`;`))[1];
const source = literal("HEAD") + literal("MAIN_OPEN") + readFileSync(stage, "utf8") + literal("CLOSE_FULL");
const work = mkdtempSync(join(tmpdir(), "stage-video-"));
const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
await page.setContent("<canvas></canvas>");
await page.evaluate(({ source, width, height }) => {
  const canvas = document.querySelector("canvas");
  canvas.width = width;
  canvas.height = height;
  const gl = canvas.getContext("webgl", { preserveDrawingBuffer: true });
  const shader = (type, text) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, text);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, "attribute vec2 a_pos;void main(){gl_Position=vec4(a_pos,0.0,1.0);}"));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, source));
  gl.linkProgram(program);
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const at = gl.getAttribLocation(program, "a_pos");
  gl.enableVertexAttribArray(at);
  gl.vertexAttribPointer(at, 2, gl.FLOAT, false, 0, 0);
  const u = (name) => gl.getUniformLocation(program, name);
  gl.uniform2f(u("u_res"), width, height);
  gl.uniform4f(u("u_box"), width / 2, height / 2, width / 2, height / 2);
  gl.uniform1f(u("u_close"), -1);
  window.drawAt = (t) => {
    gl.uniform1f(u("u_time"), t);
    gl.uniform1f(u("u_age"), t);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    return canvas.toDataURL("image/png");
  };
}, { source, width, height });
// frames -blend..count-1: the ones before the start are blended into the last ones
const frames = [];
for (let j = -blend; j < count; j++) {
  const data = await page.evaluate((t) => window.drawAt(t), 10 + j / fps);
  const file = join(work, `raw_${j + blend}.png`);
  writeFileSync(file, Buffer.from(data.split(",")[1], "base64"));
  frames.push(file);
}
await browser.close();
// frame i of the loop: its own, and over its last `blend` frames, more and more of the one just before the start
for (let i = 0; i < count; i++) {
  const own = frames[i + blend];
  const weight = i >= count - blend ? (i - (count - blend) + 1) / (blend + 1) : 0;
  if (weight === 0) execFileSync("cp", [own, join(work, `f_${String(i).padStart(4, "0")}.png`)]);
  else
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", own, "-i", frames[i + blend - count],
      "-filter_complex", `[0][1]blend=all_expr='A*(1-${weight})+B*${weight}'`, join(work, `f_${String(i).padStart(4, "0")}.png`)]);
}
execFileSync("ffmpeg", ["-v", "error", "-y", "-framerate", String(fps), "-i", join(work, "f_%04d.png"), "-c:v", "libx264",
  "-preset", "slow", "-crf", String(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", out]);
rmSync(work, { recursive: true, force: true });
console.log(`${out.split("/").pop()}: ${Math.round(readFileSync(out).length / 1024)} KB`);
