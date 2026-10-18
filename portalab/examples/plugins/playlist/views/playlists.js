// Playlists — the plugin's own page (spec 030), in Portalab's sandbox: covers made of the titles' posters
// (fetched through Portalab) or of the member's accent colours, cards on the member's tokens.

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
  root.replaceChildren(h("style", {}, `
    .lists{display:flex;flex-direction:column;gap:var(--space-4);padding:var(--space-1)}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(11rem,1fr));gap:var(--space-4)}
    .list{display:flex;flex-direction:column;gap:var(--space-2);background:none;border:0;padding:0;color:inherit;
      font:inherit;text-align:start;cursor:pointer}
    .cover{aspect-ratio:1;border-radius:var(--radius-lg);overflow:hidden;display:grid;grid-template-columns:1fr 1fr;
      background:linear-gradient(135deg,var(--color-accent),var(--color-accent-alt,var(--color-accent)));
      box-shadow:var(--shadow-sm);transition:transform var(--motion-duration-normal) var(--motion-easing)}
    .list:hover .cover,.list:focus-visible .cover{transform:scale(1.03)}
    .cover img{width:100%;height:100%;object-fit:cover;display:block}
    .cover--one img{grid-column:1/-1;grid-row:1/-1}
    .cover__letter{grid-column:1/-1;display:grid;place-items:center;font-size:3rem;font-weight:var(--font-weight-semibold);
      color:var(--color-accent-contrast)}
    .list__name{font-weight:var(--font-weight-semibold)}
    .create{display:flex;gap:var(--space-2)}
    .create .pl-input{flex:1}
  `), h("div", { class: "lists" }));
  const app = root.querySelector(".lists");

  const posterUrl = (image) => api.image(image).catch(() => null);

  async function draw() {
    const data = await api.get("mine");
    const items = data.items || [];
    const name = h("input", { class: "pl-input", placeholder: t("view.new"), "aria-label": t("view.new"), maxlength: 80 });
    const form = h("form", { class: "create", on: { submit: async (event) => {
      event.preventDefault();
      if (!name.value.trim()) return;
      await api.post("playlists", { name: name.value.trim() });
      await draw();
    } } }, name, h("button", { class: "pl-button", type: "submit" }, t("view.create")));
    const grid = h("div", { class: "grid" });
    for (const item of items) {
      const covers = (item.covers || []).slice(0, 4);
      const cover = h("div", { class: `cover${covers.length === 1 ? " cover--one" : ""}`, "aria-hidden": "true" },
        covers.length ? [] : h("span", { class: "cover__letter" }, String(item.title || "?").slice(0, 1).toUpperCase()));
      grid.append(h("button", { class: "list", type: "button", on: { click: () => api.navigate(item.link) } },
        cover, h("span", { class: "list__name" }, item.title),
        h("span", { class: "pl-muted" }, t("view.count", { count: item.count ?? 0 }))));
      Promise.all(covers.map(posterUrl)).then((urls) => {
        const shown = urls.filter(Boolean);
        if (shown.length) cover.replaceChildren(...shown.map((src) => h("img", { src, alt: "" })));
      });
    }
    app.replaceChildren(form, items.length ? grid : h("p", { class: "pl-muted" }, t("view.empty")));
  }
  draw().catch((error) => app.replaceChildren(h("p", { class: "pl-error" }, error.message)));
}
