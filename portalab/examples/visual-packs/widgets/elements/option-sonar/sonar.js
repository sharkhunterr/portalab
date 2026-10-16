// Vigie — « Le sonar »: drawn over any widget (Portalab's sandbox, pointer-events none): a sweep turning from
// the widget's corner, echoes lighting up where it passes. Nothing when the member asked for less motion.

export default function mount(root, api) {
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
  root.append(canvas);
  let context = api.context;
  let frame = 0;
  const echoes = Array.from({ length: 7 }, (_, i) => ({ a: (i / 7) * Math.PI * 2 + i, r: 0.35 + ((i * 37) % 60) / 100, lit: 0 }));
  const stop = api.onContext((next) => { context = next; start(); });
  const draw = (now) => {
    const box = root.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(box.width * ratio)) {
      canvas.width = Math.round(box.width * ratio);
      canvas.height = Math.round(box.height * ratio);
    }
    const g = canvas.getContext("2d");
    if (!g) return;
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, box.width, box.height);
    if (context.reducedMotion) return;
    const accent = (context.colors && context.colors.accent) || "#5bc0eb";
    const cx = box.width * 0.92;
    const cy = box.height * 0.88;
    const reach = Math.hypot(box.width, box.height);
    const sweep = ((now / 1000) * 0.9) % (Math.PI * 2);
    const cone = g.createConicGradient ? g.createConicGradient(sweep - 0.6, cx, cy) : null;
    if (cone) {
      cone.addColorStop(0, "rgba(0,0,0,0)");
      cone.addColorStop(0.09, `${accent}22`);
      cone.addColorStop(0.1, `${accent}55`);
      cone.addColorStop(0.101, "rgba(0,0,0,0)");
      g.fillStyle = cone;
      g.fillRect(0, 0, box.width, box.height);
    }
    for (const echo of echoes) {
      const diff = Math.abs(((sweep - echo.a + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
      if (diff > Math.PI - 0.08) echo.lit = 1;
      echo.lit *= 0.985;
      const x = cx + Math.cos(echo.a) * echo.r * reach * 0.6;
      const y = cy + Math.sin(echo.a) * echo.r * reach * 0.6;
      g.beginPath();
      g.arc(x, y, 2 + echo.lit * 2, 0, Math.PI * 2);
      g.fillStyle = `rgba(150, 255, 210, ${0.6 * echo.lit})`;
      g.fill();
    }
    frame = requestAnimationFrame(draw);
  };
  const start = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(draw); };
  start();
  return () => { cancelAnimationFrame(frame); stop(); };
}
