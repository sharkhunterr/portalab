import { useEffect, useRef, useState } from "react";
import "./external.css";

/**
 * Issue 287: a pack's video, played in its layer — once (an opening, a reveal) or over and over (a backdrop).
 * Muted, inline, never controlled by the member: a moment of the scene, not a film. ``stacked``: its upper half
 * the picture (premultiplied: black where it is transparent — the two halves blur alike as the video is
 * compressed, no dark fringe), its lower half the transparency in grey — put back together on the GPU as it
 * plays (H.264 has no transparency of its own; this way every browser plays it on its hardware decoder). Read
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
// the picture from the upper half (premultiplied), its transparency from the lower half (a little margin: the
// video's limited range never quite reaches black; the picture never brighter than its transparency allows)
const FRAGMENT = `precision mediump float;
uniform sampler2D u_video;
varying vec2 v_uv;
void main() {
  vec3 color = texture2D(u_video, vec2(v_uv.x, v_uv.y * 0.5)).rgb;
  float alpha = clamp((texture2D(u_video, vec2(v_uv.x, 0.5 + v_uv.y * 0.5)).r - 0.03) / 0.94, 0.0, 1.0);
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

/** Draws each frame of a stacked video on a canvas, the canvas sized to its box (at most the video's own). */
function stack(video: HTMLVideoElement, canvas: HTMLCanvasElement): () => void {
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
      const box = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(2, Math.min(Math.round(box.width * ratio), video.videoWidth));
      const height = Math.max(2, Math.min(Math.round(box.height * ratio), video.videoHeight / 2));
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
  alpha: "none" | "stacked";
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
    const stop = alpha === "stacked" && canvas.current ? stack(element, canvas.current) : () => {};
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
        className={alpha === "stacked" ? "visual-video visual-video--source" : "visual-video"}
        src={local ?? undefined}
        muted
        playsInline
        loop={loop}
        preload="auto"
        disablePictureInPicture
        tabIndex={-1}
        onEnded={() => setEnded(true)}
      />
      {alpha === "stacked" ? <canvas ref={canvas} className="visual-video" /> : null}
    </span>
  );
}
