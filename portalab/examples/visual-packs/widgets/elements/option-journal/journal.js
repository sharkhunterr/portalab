// Vigie — « Le journal de bord »: Portalab's « Recently added » shown as a ship's logbook. It is handed that
// widget's own data (api.context.widget.data.items: title, kind, meta, at) and the contract it declared
// (me.watching: what the member is watching) — it asks the portal nothing. One line, a column or a page: it
// writes as many entries as fit.

const WORDS = {
  fr: { title: "Journal de bord", watching: (n) => `${n} titre${n > 1 ? "s" : ""} en cours`, empty: "Rien d'arrivé pour l'instant.", kinds: { movie: "film", series: "série", episode: "épisode", book: "livre", album: "album" } },
  en: { title: "Logbook", watching: (n) => `${n} title${n === 1 ? "" : "s"} in progress`, empty: "Nothing arrived yet.", kinds: { movie: "film", series: "series", episode: "episode", book: "book", album: "album" } },
};

const escape = (text) => String(text ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export default function mount(root, api) {
  let context = api.context;
  const render = () => {
    const w = WORDS[String(context.locale || "en").slice(0, 2)] || WORDS.en;
    const items = (context.widget && context.widget.data && context.widget.data.items) || [];
    const watching = context.data && context.data["me.watching"];
    const count = watching && Array.isArray(watching.items) ? watching.items.length : null;
    const form = (context.size && context.size.form) || "block";
    const height = (context.size && context.size.height) || 160;
    const ink = "#2b1d0e";
    const time = (at) => {
      if (!at) return "";
      try { return new Date(at).toLocaleTimeString(context.locale || "en", { hour: "2-digit", minute: "2-digit" }); } catch { return ""; }
    };
    const fits = form === "line" ? 1 : Math.max(1, Math.floor((height - 46) / 26));
    const entries = items.slice(0, fits).map((item) =>
      `<li style="display:flex;gap:0.6em;align-items:baseline;border-bottom:1px solid rgba(43,29,14,0.18);padding:0.15em 0;white-space:nowrap;overflow:hidden">` +
      `<span style="font:600 0.75em ui-monospace,monospace;color:#7a4f1d">${escape(time(item.at))}</span>` +
      `<span style="flex:1;overflow:hidden;text-overflow:ellipsis;font-style:italic">${escape(item.title)}</span>` +
      `<span style="font-size:0.75em;opacity:0.7">${escape(w.kinds[item.kind] || item.kind)}${item.meta ? " · " + escape(item.meta) : ""}</span></li>`).join("");
    root.style.cssText = "box-sizing:border-box;height:100%;overflow:hidden;padding:0.6em 0.9em;border-radius:0.4em;" +
      "background:linear-gradient(180deg,#f3e6c4,#e8d4a2);box-shadow:inset 0 0 1.4em rgba(120,80,30,0.35);" +
      `color:${ink};font:14px Georgia,'Times New Roman',serif`;
    root.innerHTML = form === "line"
      ? `<div style="display:flex;gap:0.8em;align-items:center;white-space:nowrap;overflow:hidden"><strong>${escape(w.title)}</strong>${entries ? `<ul style="list-style:none;margin:0;padding:0;flex:1;min-width:0">${entries}</ul>` : `<em>${escape(w.empty)}</em>`}</div>`
      : `<div style="display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px double rgba(43,29,14,0.45);margin-bottom:0.3em">` +
        `<strong style="letter-spacing:0.06em;font-variant:small-caps">${escape(w.title)}</strong>` +
        (count != null ? `<span style="font-size:0.8em">${escape(w.watching(count))}</span>` : "") + "</div>" +
        (entries ? `<ul style="list-style:none;margin:0;padding:0">${entries}</ul>` : `<em>${escape(w.empty)}</em>`);
  };
  const stop = api.onContext((next) => { context = next; render(); });
  render();
  return stop;
}
