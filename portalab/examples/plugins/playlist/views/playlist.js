// A playlist — the plugin's own page (spec 030), filled with what the configured services know of each title
// (read through Portalab with the member's rights: library, enriched metadata, posters, artwork). Drawn on the
// member's tokens, so it follows their theme.

const h = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name === "on") for (const [event, fn] of Object.entries(value)) node.addEventListener(event, fn);
    else if (name === "class") node.className = value;
    else if (value !== undefined && value !== null && value !== false) node.setAttribute(name, value);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined) node.append(child);
  return node;
};

export default function mount(root, api) {
  const t = api.t;
  const playlist = api.params.playlist;
  root.replaceChildren(h("style", {}, `
    .playlist{display:flex;flex-direction:column;gap:var(--space-4);padding:var(--space-1)}
    .head{display:flex;flex-wrap:wrap;gap:var(--space-3);align-items:flex-end;justify-content:space-between}
    .head h2{margin:0;font-size:var(--font-size-xl,1.6rem)}
    .title{position:relative;overflow:hidden;border-radius:var(--radius-lg);border:1px solid var(--color-border);
      background:var(--color-surface-raised,var(--color-surface));box-shadow:var(--shadow-sm)}
    .title__backdrop{position:absolute;inset:0;background-size:cover;background-position:center;opacity:.22}
    .title__backdrop::after{content:"";position:absolute;inset:0;
      background:linear-gradient(90deg,var(--color-surface-raised,var(--color-surface)) 30%,transparent)}
    .title__body{position:relative;display:grid;grid-template-columns:7rem 1fr;gap:var(--space-4);padding:var(--space-4)}
    .poster{width:7rem;aspect-ratio:2/3;border-radius:var(--radius-md);object-fit:cover;cursor:pointer;
      background:linear-gradient(135deg,var(--color-accent),var(--color-accent-alt,var(--color-accent)))}
    .name{font-size:var(--font-size-lg,1.2rem);font-weight:var(--font-weight-semibold);background:none;border:0;
      padding:0;color:inherit;font-family:inherit;cursor:pointer;text-align:start}
    .name:hover{color:var(--color-accent)}
    .tagline{font-style:italic}
    .facts{display:flex;flex-wrap:wrap;gap:var(--space-2);align-items:center}
    .chip{border:1px solid var(--color-border);border-radius:var(--radius-pill);padding:0 var(--space-2);font-size:var(--font-size-xs)}
    .overview{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5}
    .cast{display:flex;gap:var(--space-2);flex-wrap:wrap}
    .person{display:flex;align-items:center;gap:var(--space-1);font-size:var(--font-size-sm)}
    .person img,.person span.face{width:1.75rem;height:1.75rem;border-radius:var(--radius-pill);object-fit:cover;
      background:var(--color-border)}
    .actions{display:flex;gap:var(--space-2);justify-content:flex-end}
    @media (max-width:560px){.title__body{grid-template-columns:4.5rem 1fr}.poster{width:4.5rem}}
  `), h("div", { class: "playlist" }));
  const app = root.querySelector(".playlist");

  const card = async (entry) => {
    const info = await api.get("details", { item: entry.item }).catch(() => null);
    const data = info && info.state === "available" ? info : { title: entry.title, genres: [] };
    const backdrop = h("div", { class: "title__backdrop", "aria-hidden": "true" });
    const poster = h("img", { class: "poster", alt: "", on: { click: () => api.navigate(`/media/${entry.item}`) } });
    const facts = [data.year, data.runtime_min ? t("view.minutes", { count: data.runtime_min }) : null,
      data.vote_average ? `★ ${Number(data.vote_average).toFixed(1)}` : null].filter(Boolean);
    const node = h("article", { class: "title" }, backdrop,
      h("div", { class: "title__body" }, poster,
        h("div", { class: "pl-stack" },
          h("button", { class: "name", type: "button", on: { click: () => api.navigate(`/media/${entry.item}`) } }, data.title || entry.title),
          data.tagline ? h("div", { class: "tagline pl-muted" }, data.tagline) : null,
          h("div", { class: "facts pl-muted" }, facts.join(" · "), ...(data.genres || []).slice(0, 4).map((g) => h("span", { class: "chip" }, g))),
          data.overview ? h("p", { class: "overview" }, data.overview) : null,
          data.director ? h("div", { class: "pl-muted" }, t("view.director", { name: data.director })) : null,
          (data.cast || []).length ? h("div", { class: "cast", "aria-label": t("view.with") },
            ...data.cast.map((person) => {
              const face = h("span", { class: "face", "aria-hidden": "true" });
              if (person.image) api.artwork(person.image, "w185").then((src) => face.replaceWith(h("img", { src, alt: "" }))).catch(() => {});
              return h("span", { class: "person", title: person.role || "" }, face, person.name);
            })) : null,
          h("div", { class: "actions" },
            h("button", { class: "pl-button", "data-variant": "ghost", type: "button", on: { click: async () => {
              await api.post("toggle", { id: playlist, item: entry.item, checked: false });
              node.remove();
            } } }, t("view.remove"))),
        )));
    if (data.image_id || entry.image_id) api.image(data.image_id || entry.image_id).then((src) => { poster.src = src; }).catch(() => {});
    if (data.backdrop) api.artwork(data.backdrop, "w1280").then((src) => { backdrop.style.backgroundImage = `url(${src})`; }).catch(() => {});
    return node;
  };

  async function draw() {
    const [list, values] = await Promise.all([
      api.get("items", { playlist }),
      api.get("values", { playlist }),
    ]);
    const meta = (values && values.values) || {};
    const head = h("header", { class: "head" },
      h("div", { class: "pl-stack" },
        h("h2", {}, meta.name || list.title || ""),
        meta.description ? h("p", { class: "pl-muted" }, meta.description) : null),
      h("div", { class: "pl-row" },
        h("button", { class: "pl-button", "data-variant": "ghost", type: "button", on: { click: () => api.open("edit", { playlist }) } }, t("view.edit")),
        h("button", { class: "pl-button", "data-variant": "ghost", type: "button", on: { click: async () => {
          try {
            const result = await api.post("delete", { playlist });
            if (result && result.link) api.navigate(result.link);
          } catch (error) { if (error.code !== "cancelled") throw error; }
        } } }, t("view.delete"))));
    const items = list.items || [];
    app.replaceChildren(head, items.length ? h("p", { class: "pl-muted" }, t("view.count", { count: items.length })) : h("p", { class: "pl-muted" }, t("view.nothing")));
    for (const node of await Promise.all(items.map(card))) app.append(node);
  }
  draw().catch((error) => app.replaceChildren(h("p", { class: "pl-error" }, error.message)));
}
