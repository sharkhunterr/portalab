// Polar fireflies — a celebration drawn by its own script. Portalab calls the default export with the
// element to draw into (it covers the screen) and the moment's context; it returns what stops it.
export default function mount(host, context) {
  if (context.reducedMotion) return () => {};
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
  host.append(canvas);
  const g = canvas.getContext("2d");
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const resize = () => {
    canvas.width = canvas.clientWidth * ratio;
    canvas.height = canvas.clientHeight * ratio;
  };
  resize();
  const colours = ["#34d399", "#5eead4", "#a78bfa", "#22d3ee", "#f0abfc"];
  const sparks = Array.from({ length: 220 }, (_, i) => {
    const angle = Math.random() * Math.PI * 2;
    const speed = 1.5 + Math.random() * 5;
    return {
      x: 0.5, y: 0.55,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 3,
      life: 0.6 + Math.random() * 1.8,
      size: 1 + Math.random() * 2.6,
      colour: colours[i % colours.length],
      wobble: Math.random() * 10,
    };
  });
  const start = performance.now();
  let frame = 0;
  const draw = (now) => {
    const t = (now - start) / 1000;
    const w = canvas.width;
    const h = canvas.height;
    g.clearRect(0, 0, w, h);
    // a soft curtain of light rising behind
    const veil = Math.max(0, Math.min(1, t * 1.5) * (1 - Math.max(0, t - 2) / 1.2));
    const gradient = g.createLinearGradient(0, h, 0, 0);
    gradient.addColorStop(0, "rgba(52,211,153,0)");
    gradient.addColorStop(0.5, `rgba(52,211,153,${0.18 * veil})`);
    gradient.addColorStop(1, `rgba(167,139,250,${0.12 * veil})`);
    g.fillStyle = gradient;
    for (let x = 0; x < w; x += 6 * ratio) {
      const top = h * (0.25 + 0.12 * Math.sin(x / (90 * ratio) + t * 2));
      g.fillRect(x, top, 5 * ratio, h - top);
    }
    g.globalCompositeOperation = "lighter";
    for (const s of sparks) {
      const age = t / s.life;
      if (age > 1) continue;
      const x = (s.x * w) / ratio + s.vx * t * 60 + Math.sin(t * 3 + s.wobble) * 12;
      const y = (s.y * h) / ratio + s.vy * t * 60 + 40 * t * t;
      g.globalAlpha = (1 - age) * (0.6 + 0.4 * Math.sin(t * 20 + s.wobble));
      g.fillStyle = s.colour;
      g.beginPath();
      g.arc(x * ratio, y * ratio, s.size * ratio, 0, Math.PI * 2);
      g.fill();
    }
    g.globalAlpha = 1;
    g.globalCompositeOperation = "source-over";
    if (t < 3.4) frame = requestAnimationFrame(draw);
  };
  frame = requestAnimationFrame(draw);
  window.addEventListener("resize", resize);
  return () => {
    cancelAnimationFrame(frame);
    window.removeEventListener("resize", resize);
    canvas.remove();
  };
}
