// Vigie — « Le cap » / « Heading »: a compass whose needle points along the member's course to the next level,
// their level in its middle; beside it their experience, coins, streak — and, with room, the last title that
// arrived. Everything it does is here: it runs in Portalab's sandbox (no network, no page of Portalab's) and
// only knows what Portalab hands it in api.context:
//   data      its contracts — me.progression, me.statistics, widget:media.recently_added (each a value, or
//             {state: "forbidden" | "loading" | "error"})
//   config    its own settings as the member chose them (dial: brass | silver | night)
//   size      {width, height, rows, form}: form is « line » (one row), « column » (narrow), « block », « tall »
//   colors, fonts, locale, reducedMotion
// and is told when any of it changes (api.onContext).

const WORDS = {
  fr: { level: "Niveau", xp: "XP", next: "Jusqu'au niveau", coins: "Pièces", streak: "Jours de suite", last: "Dernier arrivé", wait: "…", hidden: "—", cardinals: ["N", "E", "S", "O"] },
  en: { level: "Level", xp: "XP", next: "To level", coins: "Coins", streak: "Days in a row", last: "Last arrival", wait: "…", hidden: "—", cardinals: ["N", "E", "S", "W"] },
};

// the dials: the ring, the face, the marks, the needle and the words beside
const DIALS = {
  brass: { ring: ["#f6dc8f", "#a9802f", "#e5c46e", "#7b5a1c"], face: ["#1f3a5f", "#08111f"], marks: "#e8cf8a", needle: "#d8452f", cap: ["#fbe7a8", "#8a6420"], strong: "#f1d488", glow: null },
  silver: { ring: ["#ffffff", "#9aa3ad", "#e3e8ee", "#6b737c"], face: ["#2a3f63", "#0d1730"], marks: "#dfe7f1", needle: "#4aa3ff", cap: ["#ffffff", "#7d8794"], strong: "#e9eef5", glow: null },
  night: { ring: ["#3a3f47", "#16191e", "#2b3038", "#0b0d10"], face: ["#0c1512", "#030605"], marks: "#9dffcf", needle: "#9dffcf", cap: ["#2a3a33", "#0b120f"], strong: "#9dffcf", glow: "rgba(120, 255, 190, 0.85)" },
};

const isValue = (value) => value && typeof value === "object" && !("state" in value);
const escape = (text) => String(text ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export default function mount(root, api) {
  const canvas = document.createElement("canvas");
  const side = document.createElement("div");
  root.append(canvas, side);
  canvas.style.cssText = "flex:none;display:block";

  let context = api.context;
  let shown = 0; // the needle's course on screen (0…1), easing towards the real one
  let frame = 0;
  const started = performance.now();

  const words = () => WORDS[String(context.locale || "en").slice(0, 2)] || WORDS.en;
  const dial = () => DIALS[(context.config && context.config.dial) || "brass"] || DIALS.brass;
  const form = () => (context.size && context.size.form) || "block";
  const progress = () => context.data && context.data["me.progression"];
  const course = () => {
    const p = progress();
    if (!isValue(p) || p.next_level_at == null) return 1;
    const span = p.next_level_at - p.level_floor;
    return span > 0 ? Math.max(0, Math.min(1, (p.xp - p.level_floor) / span)) : 1;
  };

  // the layout of each form: where the compass goes, how big, how many lines beside
  const layout = () => {
    const box = root.getBoundingClientRect();
    const f = form();
    if (f === "line") {
      root.style.cssText = "display:flex;align-items:center;gap:0.8em;padding:0 3%;box-sizing:border-box;height:100%;overflow:hidden";
      side.style.cssText = "flex:1;min-width:0;display:flex;gap:1.2em;align-items:center;white-space:nowrap;overflow:hidden";
      return { size: Math.max(28, Math.min(box.height * 0.9, 56)), lines: 0 };
    }
    if (f === "column") {
      root.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:0.5em;padding:4% 6%;box-sizing:border-box;height:100%;overflow:hidden";
      side.style.cssText = "width:100%;display:grid;gap:0.25em;font-variant-numeric:tabular-nums";
      const size = Math.max(44, Math.min(box.width * 0.7, box.height * 0.42));
      return { size, lines: 6, room: box.height - size - box.height * 0.12 };
    }
    root.style.cssText = "display:flex;align-items:center;gap:6%;padding:0 4%;box-sizing:border-box;height:100%;overflow:hidden";
    side.style.cssText = "flex:1;min-width:0;display:grid;gap:0.35em;font-variant-numeric:tabular-nums";
    return {
      size: Math.max(40, Math.min(box.height * 0.92, box.width * 0.45)),
      lines: f === "tall" ? 6 : 5,
      room: box.height - 8,
    };
  };

  const writeSide = ({ lines, room }) => {
    const w = words();
    const d = dial();
    const p = progress();
    const figures = context.data && context.data["me.statistics"];
    const added = context.data && context.data["widget:media.recently_added"];
    const colors = context.colors || {};
    const font = (context.fonts && context.fonts.body) || "system-ui, sans-serif";
    const heading = (context.fonts && context.fonts.heading) || font;
    const text = colors.text || "#e8dcc0";
    const muted = colors["text-muted"] || "#a99f88";
    const fmt = (n) => Number(n).toLocaleString(context.locale || "en");
    const toGo = isValue(p) && p.next_level_at != null ? Math.max(0, p.next_level_at - p.xp) : null;
    if (form() === "line") {
      const bits = [
        `<strong style="color:${d.strong};font-family:${heading}">${isValue(p) ? `${w.level} ${fmt(p.level)}` : w.wait}</strong>`,
        toGo != null ? `<span style="color:${muted}">${fmt(toGo)} ${w.xp} → ${fmt(p.level + 1)}</span>` : "",
        isValue(p) ? `<span style="color:${text}">${fmt(p.coins)} ${w.coins.toLowerCase()}</span>` : "",
        isValue(figures) && figures.streak_days ? `<span style="color:${muted}">${fmt(figures.streak_days)} ${w.streak.toLowerCase()}</span>` : "",
      ];
      side.innerHTML = bits.filter(Boolean).join("");
      side.style.font = `13px ${font}`;
      return;
    }
    const line = (label, value, strong) =>
      `<div style="display:flex;justify-content:space-between;gap:0.6em;white-space:nowrap;overflow:hidden">` +
      `<span style="color:${muted};overflow:hidden;text-overflow:ellipsis">${escape(label)}</span>` +
      `<span style="color:${strong ? d.strong : text};font-weight:${strong ? 700 : 500};overflow:hidden;text-overflow:ellipsis">${escape(value)}</span></div>`;
    let html = `<div style="font:700 1.1em ${heading};color:${d.strong};letter-spacing:0.04em">${isValue(p) ? `${w.level} ${fmt(p.level)}` : w.wait}</div>`;
    const rows = [];
    if (isValue(p)) {
      rows.push(toGo == null ? line(w.xp, fmt(p.xp), false) : line(`${w.next} ${fmt(p.level + 1)}`, `${fmt(toGo)} ${w.xp}`, false));
      rows.push(line(w.coins, fmt(p.coins), true));
    }
    if (isValue(figures)) {
      const bonus = figures.streak_multiplier > 1 ? ` ×${figures.streak_multiplier}` : "";
      rows.push(line(w.streak, `${fmt(figures.streak_days)}${bonus}`, false));
    } else if (figures && figures.state === "forbidden") {
      rows.push(line(w.streak, w.hidden, false));
    }
    // with room: the last title that arrived (the « Recently added » widget's own data)
    const first = isValue(added) && added.data && Array.isArray(added.data.items) ? added.data.items[0] : null;
    if (first && lines > 4) rows.push(line(w.last, first.title, false));
    // as many lines as fit the room it has (the heading first), never cut in half
    const px = Math.max(11, Math.min(14, (room || 100) / 5.5));
    const fit = Math.max(0, Math.floor(((room || 100) - px * 1.6) / (px * 1.3 + 3)));
    html += rows.slice(0, Math.min(fit, lines - 1)).join("");
    side.innerHTML = html;
    side.style.font = `${px}px ${font}`;
    side.style.gap = "3px";
  };

  const draw = (now) => {
    const { size } = current;
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(size * ratio)) {
      canvas.width = Math.round(size * ratio);
      canvas.height = Math.round(size * ratio);
      canvas.style.width = `${size}px`;
      canvas.style.height = `${size}px`;
    }
    const g = canvas.getContext("2d");
    if (!g) return;
    const d = dial();
    const target = course();
    shown += (target - shown) * (context.reducedMotion ? 1 : 0.06);
    const t = (now - started) / 1000;
    const sway = context.reducedMotion ? 0 : Math.sin(t * 1.3) * 0.012 + Math.sin(t * 3.1) * 0.004;
    const accent = (context.colors && context.colors.accent) || "#5bc0eb";
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, size, size);
    const c = size / 2;
    const r = size / 2 - 2;
    const ring = g.createLinearGradient(0, 0, size, size);
    d.ring.forEach((colour, i) => ring.addColorStop(i / (d.ring.length - 1), colour));
    g.beginPath();
    g.arc(c, c, r, 0, Math.PI * 2);
    g.fillStyle = ring;
    g.fill();
    const face = g.createRadialGradient(c - r * 0.3, c - r * 0.35, r * 0.1, c, c, r * 0.85);
    face.addColorStop(0, d.face[0]);
    face.addColorStop(1, d.face[1]);
    g.beginPath();
    g.arc(c, c, r * 0.84, 0, Math.PI * 2);
    g.fillStyle = face;
    g.fill();
    // the course already sailed, in the interface's accent
    g.beginPath();
    g.arc(c, c, r * 0.92, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * shown);
    g.strokeStyle = accent;
    g.lineWidth = r * 0.07;
    g.lineCap = "round";
    g.stroke();
    g.shadowColor = d.glow || "transparent";
    g.shadowBlur = d.glow ? r * 0.08 : 0;
    const small = size < 60; // on one line: fewer marks, no letters
    for (let i = 0; i < 36; i += small ? 3 : 1) {
      const a = (i / 36) * Math.PI * 2;
      const long = i % 3 === 0;
      g.beginPath();
      g.moveTo(c + Math.sin(a) * r * 0.8, c - Math.cos(a) * r * 0.8);
      g.lineTo(c + Math.sin(a) * r * (long ? 0.68 : 0.74), c - Math.cos(a) * r * (long ? 0.68 : 0.74));
      g.strokeStyle = long ? d.marks : `${d.marks}88`;
      g.lineWidth = long ? 1.6 : 1;
      g.lineCap = "butt";
      g.stroke();
    }
    if (!small) {
      g.fillStyle = d.marks;
      g.font = `700 ${Math.round(r * 0.16)}px system-ui, sans-serif`;
      g.textAlign = "center";
      g.textBaseline = "middle";
      words().cardinals.forEach((letter, i) => {
        const a = (i / 4) * Math.PI * 2;
        g.fillText(letter, c + Math.sin(a) * r * 0.55, c - Math.cos(a) * r * 0.55);
      });
    }
    // the needle
    g.save();
    g.translate(c, c);
    g.rotate(Math.PI * 2 * shown + sway);
    g.shadowColor = d.glow || "rgba(0, 0, 0, 0.6)";
    g.shadowBlur = r * 0.08;
    const wide = r * 0.09;
    g.beginPath();
    g.moveTo(0, -r * 0.62);
    g.lineTo(wide, 0);
    g.lineTo(-wide, 0);
    g.closePath();
    g.fillStyle = d.needle;
    g.fill();
    g.beginPath();
    g.moveTo(0, r * 0.42);
    g.lineTo(wide, 0);
    g.lineTo(-wide, 0);
    g.closePath();
    g.fillStyle = "#e9e4d6";
    g.fill();
    g.restore();
    g.shadowBlur = 0;
    // the cap: the level
    const capR = r * 0.26;
    const cap = g.createRadialGradient(c - capR * 0.3, c - capR * 0.4, capR * 0.1, c, c, capR);
    cap.addColorStop(0, d.cap[0]);
    cap.addColorStop(1, d.cap[1]);
    g.beginPath();
    g.arc(c, c, capR, 0, Math.PI * 2);
    g.fillStyle = cap;
    g.fill();
    const p = progress();
    g.fillStyle = d.glow ? d.strong : "#2e1f06";
    g.font = `800 ${Math.round(capR * 0.95)}px system-ui, sans-serif`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(isValue(p) ? String(p.level) : "·", c, c + capR * 0.05);
    if (!context.reducedMotion || Math.abs(target - shown) > 0.001) frame = requestAnimationFrame(draw);
  };

  let current = layout();
  const restart = () => {
    cancelAnimationFrame(frame);
    current = layout();
    writeSide(current);
    frame = requestAnimationFrame(draw);
  };
  const stopListening = api.onContext((next) => {
    context = next;
    restart();
  });
  restart();
  return () => {
    cancelAnimationFrame(frame);
    stopListening();
  };
}
