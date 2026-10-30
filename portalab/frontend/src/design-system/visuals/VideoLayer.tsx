import { useEffect, useRef, useState } from "react";
import "./external.css";

/**
 * Issue 287: a pack's video, played in its layer — once (an opening, a reveal) or over and over (a backdrop).
 * Muted, inline, never controlled by the member: a moment of the scene, not a film. ``side`` / ``stacked``: the
 * picture in its left / upper half (premultiplied: black where it is transparent — the two halves blur alike as
 * the video is compressed, no dark fringe), the transparency in grey in its right / lower half — put back
 * together on the GPU as it plays (H.264 has no transparency of its own; this way every browser plays it on its
 * hardware decoder; side by side, a tall layer's video stays within the 4K phones decode). Read
 * once, kept for the page's life (a booster's videos are preloaded with its scene, so they start at once);
 * played once, it leaves nothing behind (its last frame is not held).
 */

const sources = new Map<string, Promise<string | null>>();

/** The video's local address once read (``null``: it could not be). */
export function preloadVideo(url: string): Promise<string | null> {
  let known = sources.get(url);
  if (!known) {
    known = fetch(url, { credentials: "same-origin" })
      .then((response) => (response.ok ? response.blob() : null))
      .then((blob) => (blob ? URL.createObjectURL(blob) : null))
      .catch(() => null);
    sources.set(url, known);
  }
  return known;
}

const VERTEX = `attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = vec2(a_pos.x * 0.5 + 0.5, 0.5 - a_pos.y * 0.5);
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;
// the picture from one half (premultiplied), its transparency from the other (``u_half``: where it starts — a
// little margin: the video's limited range never quite reaches black; the picture never brighter than its
// transparency allows); ``u_cover``: the part of the picture its box shows, cropped to cover it (issue 290)
const FRAGMENT = `precision mediump float;
uniform sampler2D u_video;
uniform vec2 u_half;
uniform vec2 u_cover;
varying vec2 v_uv;
void main() {
  vec2 at = (0.5 + (v_uv - 0.5) * u_cover) * (vec2(1.0) - u_half);
  vec3 color = texture2D(u_video, at).rgb;
  float alpha = clamp((texture2D(u_video, at + u_half).r - 0.03) / 0.94, 0.0, 1.0);
  gl_FragColor = vec4(min(color, vec3(alpha)), alpha);
}`;

function program(gl: WebGLRenderingContext): WebGLProgram | null {
  const shader = (type: number, source: string) => {
    const s = gl.createShader(type);
    if (!s) return null;
    gl.shaderSource(s, source);
    gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  };
  const vertex = shader(gl.VERTEX_SHADER, VERTEX);
  const fragment = shader(gl.FRAGMENT_SHADER, FRAGMENT);
  const linked = gl.createProgram();
  if (!vertex || !fragment || !linked) return null;
  gl.attachShader(linked, vertex);
  gl.attachShader(linked, fragment);
  gl.linkProgram(linked);
  return gl.getProgramParameter(linked, gl.LINK_STATUS) ? linked : null;
}

type Alpha = "none" | "side" | "stacked";

/** Draws each frame of a video holding its transparency on a canvas, sized to its box (at most the video's). */
function recompose(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  alpha: Exclude<Alpha, "none">,
): () => void {
  const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
  const linked = gl ? program(gl) : null;
  if (!gl || !linked) return () => {};
  // biome-ignore lint/correctness/useHookAtTopLevel: WebGL's useProgram, not a React hook
  gl.useProgram(linked);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(linked, "a_pos");
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  const side = alpha === "side";
  gl.uniform2f(gl.getUniformLocation(linked, "u_half"), side ? 0.5 : 0, side ? 0 : 0.5);
  const cover = gl.getUniformLocation(linked, "u_cover");
  gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  let stopped = false;
  let frame = 0;
  const draw = () => {
    if (stopped) return;
    if (video.readyState >= 2 && video.videoWidth) {
      // the canvas its box's shape, no larger than the picture shown in it; the picture cropped to cover it
      const box = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const pictureW = video.videoWidth / (side ? 2 : 1);
      const pictureH = video.videoHeight / (side ? 1 : 2);
      const boxW = Math.max(1, box.width * ratio);
      const boxH = Math.max(1, box.height * ratio);
      const fit = Math.min(1, Math.max(pictureW / boxW, pictureH / boxH));
      const width = Math.max(2, Math.round(boxW * fit));
      const height = Math.max(2, Math.round(boxH * fit));
      const shape = boxW / boxH / (pictureW / pictureH);
      gl.uniform2f(cover, shape > 1 ? 1 : shape, shape > 1 ? 1 / shape : 1);
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, video);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    next();
  };
  // a new frame when the video has one (or on each of the screen's, where that is not offered)
  const next = () => {
    if (stopped) return;
    if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(draw);
    else frame = requestAnimationFrame(draw);
  };
  next();
  return () => {
    stopped = true;
    cancelAnimationFrame(frame);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  };
}

export function VideoLayer({
  src,
  alpha,
  loop,
  className,
  over,
}: {
  src: string;
  alpha: Alpha;
  loop: boolean;
  className: string;
  /** a reveal's second video, drawn over the card */
  over?: boolean;
}) {
  const [local, setLocal] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [ended, setEnded] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    let live = true;
    void preloadVideo(src).then((address) => {
      if (!live) return;
      if (address) setLocal(address);
      else setFailed(true);
    });
    return () => {
      live = false;
    };
  }, [src]);
  useEffect(() => {
    const element = video.current;
    if (!local || !element) return;
    const stop = alpha !== "none" && canvas.current ? recompose(element, canvas.current, alpha) : () => {};
    element.currentTime = 0;
    element.play().catch(() => setFailed(true));
    return () => {
      stop();
      element.pause();
    };
  }, [local, alpha]);
  if (failed || ended) return null;
  return (
    <span className={className} aria-hidden="true" data-over={over || undefined}>
      <video
        ref={video}
        className={alpha === "none" ? "visual-video" : "visual-video visual-video--source"}
        src={local ?? undefined}
        muted
        playsInline
        loop={loop}
        preload="auto"
        disablePictureInPicture
        tabIndex={-1}
        onEnded={() => setEnded(true)}
      />
      {alpha === "none" ? null : <canvas ref={canvas} className="visual-video" />}
    </span>
  );
}
