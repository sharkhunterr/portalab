// Sonar — a navigation of its own, for the Abysses interface. It runs in Portalab's sandbox: it knows the
// sections and pages it is given (keys, names, icons — never addresses) and asks Portalab to open one with
// api.navigate(key); api.expand(true) lets it cover the screen while open.
//
// Folded: a bar along the bottom — the sonar button (its beam sweeping), where one is, an echo per section.
// Open: the sonar sweeps the depths; each section is an echo round the centre, its pages rise as bubbles.
// Keyboard: Tab between echoes and bubbles, Enter opens, Escape closes; reduced motion: nothing sweeps.

const CSS = `
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.3 var(--body); color: var(--text); }
button { font: inherit; color: inherit; cursor: pointer; }
button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.bar { position: fixed; inset: 0; display: flex; align-items: center; gap: 12px; padding: 0 14px;
  background: linear-gradient(180deg, rgba(2,12,24,.82), rgba(1,6,14,.96));
  border-top: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
  box-shadow: 0 -12px 30px rgba(0,30,60,.45); }
.ping { position: relative; flex: none; width: 54px; height: 54px; border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--accent) 70%, transparent);
  background: radial-gradient(circle, rgba(0,40,60,.9) 0 60%, rgba(0,20,35,.95));
  overflow: hidden; }
.ping::before, .big .beam { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, color-mix(in srgb, var(--accent) 75%, transparent), transparent 70deg);
  animation: sweep 3s linear infinite; }
.ping::after { content: ""; position: absolute; inset: 22px; border-radius: 50%; background: var(--accent);
  box-shadow: 0 0 12px var(--accent); }
.ping .count { position: absolute; top: 3px; right: 3px; z-index: 2; min-width: 18px; padding: 0 4px;
  border-radius: 9px; background: var(--alt); color: #001018; font-size: 11px; font-weight: 700; line-height: 18px; }
@keyframes sweep { to { transform: rotate(1turn); } }
.where { flex: 1; min-width: 0; }
.where b { display: block; font-family: var(--heading); letter-spacing: .04em; color: var(--accent);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.where span { display: block; font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.echoes { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; max-width: 60%; }
.echo { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
  background: rgba(0, 30, 50, .65); }
.echo[aria-current="true"] { border-color: var(--accent); box-shadow: 0 0 14px color-mix(in srgb, var(--accent) 60%, transparent); }
.echo svg, .blip svg, .bubble svg { width: 20px; height: 20px; }
.big { position: fixed; inset: 0; display: grid; place-items: center;
  background: radial-gradient(circle at 50% 55%, rgba(0,40,70,.94), rgba(0,6,16,.97) 70%); }
.scope { position: relative; width: min(92vmin, 680px); aspect-ratio: 1; border-radius: 50%; }
.scope .ring { position: absolute; border-radius: 50%; border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent); }
.scope .beam { opacity: .55; }
.blip { position: absolute; transform: translate(-50%, -50%); display: grid; justify-items: center; gap: 4px;
  min-width: 64px; padding: 8px 10px; border-radius: 16px; border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  background: rgba(0, 24, 40, .82); text-align: center; font-size: 13px; animation: appear .5s both; }
.blip[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); box-shadow: 0 0 22px color-mix(in srgb, var(--accent) 55%, transparent); }
.blip[data-here] { outline: 1px dashed color-mix(in srgb, var(--alt) 70%, transparent); outline-offset: 3px; }
@keyframes appear { from { opacity: 0; transform: translate(-50%, -50%) scale(.6); } }
.pages { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); display: grid; gap: 8px;
  width: min(62%, 300px); max-height: 52%; overflow-y: auto; padding: 4px; }
.pages h2 { margin: 0 0 4px; text-align: center; font: 600 17px/1.2 var(--heading); color: var(--accent); }
.bubble { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 14px; border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); background: rgba(0, 40, 64, .9);
  text-align: left; animation: rise .45s both; }
.bubble[aria-current="page"] { border-color: var(--accent); color: var(--accent); }
@keyframes rise { from { opacity: 0; transform: translateY(18px); } }
.close { position: fixed; top: 14px; right: 14px; width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent); background: rgba(0,20,35,.9); font-size: 22px; }
@media (max-width: 560px) { .where span { display: none; } .echoes { max-width: 52%; } .blip { min-width: 54px; font-size: 11.5px; padding: 6px 8px; } }
@media (prefers-reduced-motion: reduce) { .ping::before, .big .beam, .blip, .bubble { animation: none; } }
.still .ping::before, .still .big .beam, .still .blip, .still .bubble { animation: none; }
`;

function el(tag, attributes = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === undefined || value === null || value === false) continue;
    if (name === "text") node.textContent = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? "" : String(value));
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

function icon(markup) {
  // the icons come from Portalab (its own SVG markup)
  const holder = el("span", { "aria-hidden": "true" });
  holder.innerHTML = markup || "";
  return holder;
}

export default function mount(root, api) {
  let context = api.context;
  let open = false;
  let chosen = null;
  const style = el("style");
  document.head.append(style);

  const paint = () => {
    const c = context.colors || {};
    style.textContent = `:root{--accent:${c.accent || "#2dd4bf"};--alt:${c["accent-alt"] || "#a78bfa"};` +
      `--text:${c.text || "#e0f7ff"};--muted:${c["text-muted"] || "#8fb4c8"};--focus:${c.focus || "#fbbf24"};` +
      `--heading:"Abysses Righteous",${(context.fonts || {}).heading || "sans-serif"};` +
      `--body:${(context.fonts || {}).body || "system-ui,sans-serif"};}${CSS}`;
    document.documentElement.classList.toggle("still", Boolean(context.reducedMotion));
  };

  const sections = () => context.sections || [];
  const here = () => sections().find((s) => s.active) || sections()[0];
  const hereEntry = () => {
    const section = here();
    return section && (section.entries.find((e) => e.active) || null);
  };

  const pick = (section) => {
    if (!section) return;
    if (section.entries.length <= 1) {
      api.navigate(section.entries[0] ? section.entries[0].key : section.key);
      setOpen(false);
      return;
    }
    chosen = section.key;
    setOpen(true);
  };

  const bar = () => {
    const section = here();
    const entry = hereEntry();
    const unread = (context.counts || {}).unread || 0;
    return el("div", { class: "bar" }, [
      el("button", {
        class: "ping", type: "button",
        "aria-label": (context.strings || {}).open || "Open navigation",
        "aria-expanded": "false",
        onclick: () => { chosen = null; setOpen(true); },
      }, [unread ? el("span", { class: "count", text: unread > 99 ? "99+" : String(unread) }) : null]),
      el("div", { class: "where" }, [
        el("b", { text: section ? section.label : "" }),
        el("span", { text: entry ? entry.label : "" }),
      ]),
      el("div", { class: "echoes", role: "list" }, sections().map((s) =>
        el("button", {
          class: "echo", type: "button", role: "listitem", title: s.label, "aria-label": s.label,
          "aria-current": s.active ? "true" : undefined,
          onclick: () => pick(s),
        }, [icon(s.icon)]))),
    ]);
  };

  const big = () => {
    const list = sections();
    const selected = list.find((s) => s.key === chosen);
    const scope = el("div", { class: "scope" }, [
      ...[0.32, 0.62, 0.92].map((r) => el("span", { class: "ring", style: `inset:${(1 - r) * 50}%` })),
      el("span", { class: "beam" }),
    ]);
    list.forEach((s, index) => {
      const angle = (index / list.length) * Math.PI * 2 - Math.PI / 2;
      const radius = 40;
      scope.append(el("button", {
        class: "blip", type: "button",
        style: `left:${50 + Math.cos(angle) * radius}%;top:${50 + Math.sin(angle) * radius}%;animation-delay:${index * 60}ms`,
        "aria-pressed": s.key === chosen ? "true" : "false",
        "data-here": s.active || undefined,
        onclick: () => pick(s),
      }, [icon(s.icon), el("span", { text: s.label })]));
    });
    if (selected) {
      scope.append(el("div", { class: "pages", role: "list", "aria-label": selected.label }, [
        el("h2", { text: selected.label }),
        ...selected.entries.map((e, index) => el("button", {
          class: "bubble", type: "button", role: "listitem", style: `animation-delay:${index * 50}ms`,
          "aria-current": e.active ? "page" : undefined,
          onclick: () => { api.navigate(e.key); setOpen(false); },
        }, [icon(e.icon), el("span", { text: e.label })])),
      ]));
    }
    return el("div", { class: "big", role: "dialog", "aria-modal": "true", "aria-label": (context.strings || {}).mainNav || "Navigation" }, [
      scope,
      el("button", { class: "close", type: "button", "aria-label": (context.strings || {}).close || "Close", text: "×", onclick: () => setOpen(false) }),
    ]);
  };

  const render = () => {
    paint();
    root.replaceChildren(open ? big() : bar());
    if (open) (root.querySelector('.blip[aria-pressed="true"]') || root.querySelector(".blip"))?.focus();
  };

  function setOpen(next) {
    if (open === next) return render();
    open = next;
    api.expand(open);
    render();
  }

  const onKey = (event) => {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      root.querySelector(".ping")?.focus();
    }
  };
  document.addEventListener("keydown", onKey);
  const stop = api.onContext((next) => {
    context = next;
    render();
  });
  // the pack's own font, handed by Portalab
  api.asset("Righteous.woff2").then((url) => {
    const face = new FontFace("Abysses Righteous", `url(${url})`);
    return face.load().then((loaded) => { document.fonts.add(loaded); render(); });
  }).catch(() => {});
  render();
  return () => {
    stop();
    document.removeEventListener("keydown", onKey);
    root.replaceChildren();
  };
}
