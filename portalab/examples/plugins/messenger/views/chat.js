// Messenger — the plugin's own chat panel (spec 030), in Portalab's sandbox: no network, only `api`. Bubbles,
// a list of conversations and a composer, all drawn with the member's tokens; new messages arrive live.

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
const time = (iso, language) =>
  new Intl.DateTimeFormat(language || "en", { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));

export default function mount(root, api) {
  const t = api.t;
  root.replaceChildren(h("style", {}, `
    html,body,#root{height:100%}
    .chat{display:flex;flex-direction:column;height:100%}
    .chat__top{display:flex;align-items:center;gap:var(--space-2);padding:var(--space-2) var(--space-1)}
    .chat__list{flex:1;overflow:auto;display:flex;flex-direction:column;gap:var(--space-1);padding:var(--space-1)}
    .person{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-2);border-radius:var(--radius-md);
      background:transparent;border:0;color:inherit;font:inherit;text-align:start;cursor:pointer;width:100%}
    .person:hover{background:var(--color-surface-raised,var(--color-surface))}
    .person__name{flex:1;font-weight:var(--font-weight-medium)}
    .avatar{width:2.25rem;height:2.25rem;border-radius:var(--radius-pill);display:grid;place-items:center;flex:none;
      background:linear-gradient(135deg,var(--color-accent),var(--color-accent-alt,var(--color-accent)));
      color:var(--color-accent-contrast);font-size:var(--font-size-sm);font-weight:var(--font-weight-semibold)}
    .bubbles{flex:1;overflow:auto;display:flex;flex-direction:column;gap:var(--space-2);padding:var(--space-2)}
    .bubble{max-width:80%;padding:var(--space-2) var(--space-3);white-space:pre-wrap;align-self:flex-start}
    .bubble[data-mine]{align-self:flex-end}
    /* the plain look of the bubbles, kept below any look chosen in Appearance (no specificity: a look wins) */
    :where(.bubble){background:var(--color-surface-raised,var(--color-surface));border:1px solid var(--color-border);
      border-radius:var(--radius-lg)}
    :where(.bubble[data-mine]){background:var(--color-accent);color:var(--color-accent-contrast);border-color:transparent}
    .bubble small{display:block;opacity:.7;font-size:var(--font-size-xs);margin-top:var(--space-1)}
    .composer{display:flex;gap:var(--space-2);padding:var(--space-2);border-top:1px solid var(--color-border)}
    .composer{flex-wrap:wrap}
    .composer .pl-input{flex:1;min-width:8rem}
    .composer .pl-input[data-to]{flex-basis:100%}
    [hidden]{display:none!important}
  `), h("div", { class: "chat" }));
  const app = root.querySelector(".chat");
  let open = api.params.conversation || null;
  // the look of the member's own bubbles: a pack's look of this plugin's kind « bubble », bought in the shop
  // and chosen in Portalab's Appearance page (handed in the context, again whenever the member changes it)
  const bubbleStyle = document.createElement("style");
  document.head.append(bubbleStyle);
  let bubble = null;
  const wear = async () => {
    const chosen = (api.context.looks && api.context.looks.bubble) || null;
    if (chosen === bubble) return;
    bubble = chosen;
    bubbleStyle.textContent = bubble ? await api.look("bubble", bubble).catch(() => "") : "";
    for (const mine of app.querySelectorAll(".bubble[data-mine]")) {
      if (bubble) mine.setAttribute("data-bubble", bubble);
      else mine.removeAttribute("data-bubble");
    }
  };

  const composer = (placeholder, send, extra = []) => {
    const input = h("input", { class: "pl-input", placeholder, "aria-label": placeholder, maxlength: 2000 });
    const button = h("button", { class: "pl-button", type: "submit" }, t("action.send"));
    const status = h("p", { role: "status", class: "pl-error", hidden: true });
    return h("div", {}, status, h("form", { class: "composer", on: { submit: async (event) => {
      event.preventDefault();
      if (!input.value.trim()) return;
      button.disabled = true;
      status.hidden = true;
      try {
        const result = await send(input.value.trim(), extra.map((e) => e.value.trim()));
        if (result && result.state === "error") { status.textContent = result.message; status.hidden = false; }
        else input.value = "";
      } catch (error) {
        if (error.code !== "cancelled") { status.textContent = error.message; status.hidden = false; }
      } finally {
        button.disabled = false;
        input.focus();
      }
    } } }, extra, input, button));
  };

  async function conversations() {
    open = null;
    const data = await api.get("conversations");
    const items = data.items || [];
    const to = h("input", { class: "pl-input", "data-to": "", placeholder: t("view.to"), "aria-label": t("view.to"), maxlength: 64 });
    app.replaceChildren(
      h("div", { class: "chat__list" },
        items.length
          ? items.map((item) => h("button", { class: "person", type: "button", on: { click: () => conversation(item.id) } },
              h("span", { class: "avatar", "aria-hidden": "true" }, initials(item.label)),
              h("span", { class: "person__name" }, item.label),
              item.unread ? h("span", { class: "pl-badge" }, String(item.unread)) : null))
          : h("p", { class: "pl-muted" }, t("view.empty")),
      ),
      h("div", { class: "pl-muted", style: "padding:0 var(--space-2)" }, t("view.new")),
      composer(t("view.placeholder"), async (body, [name]) => {
        const result = await api.post("send", { to: name, body });
        if (result && result.conversation) await conversation(result.conversation);
        return result;
      }, [to]),
    );
  }

  async function conversation(id) {
    open = id;
    const data = await api.get("messages", { conversation: id });
    const bubbles = h("div", { class: "bubbles", "aria-live": "polite" },
      (data.items || []).map((item) => h("div", { class: "bubble", "data-mine": item.mine ? "" : null, "data-bubble": item.mine && bubble ? bubble : null },
        item.body, h("small", {}, `${item.mine ? "" : `${item.author} · `}${time(item.at, api.context.language)}`))));
    app.replaceChildren(
      h("div", { class: "chat__top" },
        h("button", { class: "pl-button", "data-variant": "ghost", type: "button", on: { click: conversations } }, "←"),
        h("span", { class: "avatar", "aria-hidden": "true" }, initials(data.title)),
        h("strong", {}, data.title || "")),
      bubbles,
      composer(t("view.placeholder"), (body) => api.post("send", { conversation: id, body }).then(async (result) => {
        await conversation(id);
        return result;
      })),
    );
    bubbles.scrollTop = bubbles.scrollHeight;
  }

  api.subscribe("new", (event) => {
    const payload = event && typeof event === "object" ? event : {};
    if (open && String(payload.conversation) === String(open)) conversation(open);
    else if (!open) conversations();
  });
  api.onContext(() => { wear(); });
  wear().then(() => (open ? conversation(open) : conversations())).catch((error) => app.replaceChildren(h("p", { class: "pl-error" }, error.message)));
}
