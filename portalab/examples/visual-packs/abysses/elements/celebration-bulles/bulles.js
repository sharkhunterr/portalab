// Bubbles from the deep — a celebration drawn by its own script, in Portalab's sandbox (no network, no
// page of Portalab's): it draws into the element it is given and returns what stops it.
export default function mount(root, api) {
  if (api.reducedMotion) return () => {};
  const canvas = document.createElement("canvas");
  canvas.style.position = "absolute";
  canvas.style.inset = "0";
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  root.append(canvas);
  const g = canvas.getContext("2d");
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const fit = () => {
    canvas.width = canvas.clientWidth * ratio;
    canvas.height = canvas.clientHeight * ratio;
  };
  fit();
  const bubbles = Array.from({ length: 140 }, () => ({
    x: 0.5 + (Math.random() - 0.5) * 0.25,
    size: 2 + Math.random() * 9,
    speed: 0.12 + Math.random() * 0.3,
    wobble: Math.random() * 10,
    delay: Math.random() * 0.9,
  }));
  const start = performance.now();
  let frame = 0;
  const draw = (now) => {
    const t = (now - start) / 1000;
    const w = canvas.width;
    const h = canvas.height;
    g.clearRect(0, 0, w, h);
    for (const b of bubbles) {
      const life = t - b.delay;
      if (life < 0) continue;
      const y = h * (0.62 - life * b.speed);
      if (y < -20) continue;
      const x = w * (b.x + (b.x - 0.5) * life * 0.8) + Math.sin(life * 4 + b.wobble) * 8 * ratio;
      const r = b.size * ratio * (1 + life * 0.2);
      const fade = Math.max(0, 1 - life / 2.8);
      g.globalAlpha = fade;
      g.strokeStyle = "rgba(180, 250, 255, 0.9)";
      g.lineWidth = 1.2 * ratio;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.stroke();
      g.fillStyle = "rgba(94, 234, 212, 0.18)";
      g.fill();
      g.fillStyle = "rgba(255, 255, 255, 0.8)";
      g.beginPath();
      g.arc(x - r * 0.35, y - r * 0.35, r * 0.22, 0, Math.PI * 2);
      g.fill();
    }
    g.globalAlpha = 1;
    if (t < 3.2) frame = requestAnimationFrame(draw);
  };
  frame = requestAnimationFrame(draw);
  window.addEventListener("resize", fit);
  return () => {
    cancelAnimationFrame(frame);
    window.removeEventListener("resize", fit);
    canvas.remove();
  };
}
