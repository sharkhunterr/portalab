// Forum — the plugin's own view (spec 030). It runs in Portalab's sandbox: no network, only `api`. Its look is
// its own, built on the member's tokens (var(--color-…), var(--radius-…)) so it follows their theme.

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

const initials = (name) => String(name || "?").split(/\s+/).map((p) => p[0] || "").join("").slice(0, 2).toUpperCase();
const when = (iso, language) => {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const units = [["day", 86400], ["hour", 3600], ["minute", 60]];
  const format = new Intl.RelativeTimeFormat(language || "en", { numeric: "auto" });
  for (const [unit, size] of units) if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  return format.format(0, "minute");
};

export default function mount(root, api) {
  const t = api.t;
  const language = () => api.context.language;
  const style = h("style", {}, `
    .forum{display:flex;flex-direction:column;gap:var(--space-4);padding:var(--space-1)}
    .forum__bar{display:flex;gap:var(--space-2);align-items:center}
    .forum__bar .pl-input{flex:1}
    .topic{display:grid;grid-template-columns:auto 1fr auto;gap:var(--space-3);align-items:center;cursor:pointer;
      text-align:start;width:100%;font:inherit;color:inherit;transition:transform var(--motion-duration-fast) var(--motion-easing)}
    .topic:hover{transform:translateY(-1px);border-color:var(--color-accent)}
    .avatar{width:2.5rem;height:2.5rem;border-radius:var(--radius-pill);display:grid;place-items:center;font-weight:var(--font-weight-semibold);
      background:linear-gradient(135deg,var(--color-accent),var(--color-accent-alt,var(--color-accent)));color:var(--color-accent-contrast)}
    .topic__title{font-size:var(--font-size-lg,1.1rem);font-weight:var(--font-weight-semibold)}
    .topic__count{min-width:3rem;text-align:center}
    .message{display:grid;grid-template-columns:auto 1fr;gap:var(--space-3)}
    .message__body{white-space:pre-wrap;line-height:1.5}
    .composer{display:flex;flex-direction:column;gap:var(--space-2)}
    [hidden]{display:none!important}
  `);
  const app = h("div", { class: "forum" });
  root.replaceChildren(style, app);

  const composer = (fields, label, onSend) => {
    const inputs = fields.map((field) =>
      field.multiline
        ? h("textarea", { class: "pl-textarea", placeholder: field.placeholder, "aria-label": field.label, maxlength: field.max })
        : h("input", { class: "pl-input", placeholder: field.label, "aria-label": field.label, maxlength: field.max }),
    );
    const status = h("p", { role: "status", class: "pl-muted" });
    const send = h("button", { class: "pl-button", type: "submit" }, label);
    const form = h("form", { class: "composer pl-card", on: { submit: async (event) => {
      event.preventDefault();
      send.disabled = true;
      status.textContent = "";
      try {
        const result = await onSend(inputs.map((input) => input.value.trim()));
        if (result && result.state === "error") status.textContent = result.message || "";
        else inputs.forEach((input) => { input.value = ""; });
      } catch (error) {
        if (error.code !== "cancelled") status.textContent = error.message;
      } finally {
        send.disabled = false;
      }
    } } }, inputs, h("div", { class: "pl-row" }, send, status));
    return form;
  };

  async function topics() {
    const data = await api.get("topics");
    const items = data.items || [];
    const search = h("input", { class: "pl-input", type: "search", placeholder: t("view.search"), "aria-label": t("view.search") });
    const list = h("div", { class: "pl-stack" });
    const draw = () => {
      const query = search.value.trim().toLowerCase();
      const shown = items.filter((item) => !query || String(item.label).toLowerCase().includes(query));
      list.replaceChildren(
        ...(shown.length ? shown : []).map((item) =>
          h("button", { class: "topic pl-card", type: "button", on: { click: () => api.navigate(item.link) } },
            h("span", { class: "avatar", "aria-hidden": "true" }, initials(item.author)),
            h("span", {}, h("div", { class: "topic__title" }, item.label),
              h("div", { class: "pl-muted" }, `${item.author || ""} · ${item.last_at ? when(item.last_at, language()) : ""}`)),
            h("span", { class: "topic__count pl-badge", title: t("view.replies", { count: item.replies ?? 0 }) }, String(item.replies ?? 0)),
          ),
        ),
      );
      if (!shown.length) list.append(h("p", { class: "pl-muted" }, t("view.empty")));
    };
    search.addEventListener("input", draw);
    const write = composer(
      [{ label: t("field.title"), max: 120 }, { label: t("field.body"), placeholder: t("view.placeholder"), multiline: true, max: 4000 }],
      t("action.publish"),
      async ([title, body]) => {
        const result = await api.post("topics", { title, body });
        if (result && result.link) api.navigate(result.link);
        return result;
      },
    );
    write.hidden = true;
    const toggle = h("button", { class: "pl-button", type: "button", on: { click: () => {
      write.hidden = !write.hidden;
      toggle.textContent = write.hidden ? t("view.new") : t("view.cancel");
    } } }, t("view.new"));
    app.replaceChildren(h("div", { class: "forum__bar" }, search, toggle), write, list);
    draw();
  }

  async function thread(topic) {
    const data = await api.get("thread", { topic });
    const back = h("button", { class: "pl-button", "data-variant": "ghost", type: "button", on: { click: () => api.navigate("/plugins/forum/topics") } }, `← ${t("view.back")}`);
    const messages = h("div", { class: "pl-stack" },
      (data.items || []).map((item) =>
        h("article", { class: "message pl-card" },
          h("span", { class: "avatar", "aria-hidden": "true" }, initials(item.author)),
          h("div", {},
            h("div", { class: "pl-muted" }, `${item.author} · ${when(item.at, language())}`),
            h("div", { class: "message__body" }, item.removed ? "—" : item.body),
          ),
        ),
      ),
    );
    const reply = composer(
      [{ label: t("field.body"), placeholder: t("view.placeholder"), multiline: true, max: 4000 }],
      t("action.reply"),
      async ([body]) => {
        const result = await api.post("replies", { topic, body });
        if (!result || result.state !== "error") await thread(topic);
        return result;
      },
    );
    app.replaceChildren(back, h("h2", {}, data.title || ""), messages, reply);
  }

  const start = () => (api.params.topic ? thread(api.params.topic) : topics());
  start().catch((error) => app.replaceChildren(h("p", { class: "pl-error" }, error.message)));
}
