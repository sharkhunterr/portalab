"""A plugin's own views (spec 030, owner's request of 2026-10-18): its pages, modals, drawers, panels and
launchers drawn by the plugin itself — in the sandbox of spec 028, never in Portalab's page.

A view is a JavaScript module of the plugin's package (``views/…``) run in a frame of an opaque origin: no
session, no cookie, no storage of Portalab's, no network (``connect-src 'none'``), no form, popup or
navigation of the page. It sees what Portalab hands it (its parameters, the theme's tokens, the language, the
plugin's own messages) and acts only through Portalab: ``api.call`` reaches **its own plugin's routes** as the
member (a committing one is confirmed in Portalab's own dialog, above the view), ``api.subscribe`` its own
live topics, ``api.open``/``api.close``/``api.navigate`` its own surfaces and pages or a title's page.
Portalab keeps the frame around it (the plugin's name, closing) so a view cannot pass itself off as Portalab.
"""

import base64
import hashlib

VIEW_BOOTSTRAP = r"""
"use strict";
(() => {
  const host = window.parent;
  let mounted = null;
  let next = 0;
  const waiting = new Map();
  const topics = new Map();
  const listeners = new Set();
  let context = {};
  const send = (message, transfer) => host.postMessage(message, "*", transfer || []);
  const ask = (message) => new Promise((resolve, reject) => {
    const id = ++next;
    waiting.set(id, { resolve, reject });
    send({ ...message, id });
  });
  const asset = (path) => ask({ type: "asset", path: String(path) }).then(
    (answer) => URL.createObjectURL(new Blob([answer.buffer], { type: String(answer.mime || "") })),
  );
  // the member's theme, interface and palette: Portalab's tokens as CSS variables, its base kit on them;
  // given again whenever the member changes them, so a view keeps following them
  const themeStyle = document.createElement("style");
  document.head.appendChild(themeStyle);
  const applyTheme = () => {
    let css = ":root{";
    for (const [name, value] of Object.entries(context.tokens || {})) {
      if (/^--[a-z0-9-]+$/.test(name)) css += name + ":" + String(value).replace(/[;{}<>\\]/g, "") + ";";
    }
    css += "color-scheme:" + (context.scheme === "dark" ? "dark" : "light") + "}";
    themeStyle.textContent = css + String(context.kit || "");
    document.documentElement.dataset.theme = String(context.theme || "");
    document.documentElement.lang = String(context.language || "en");
    document.documentElement.dir = context.direction === "rtl" ? "rtl" : "ltr";
  };
  // a poster of the portal's library (``image_id`` of a title), read by Portalab with the member's rights
  const image = (id) => ask({ type: "image", image: String(id) }).then(
    (answer) => URL.createObjectURL(new Blob([answer.buffer], { type: String(answer.mime || "") })),
  );
  // a title's artwork (a ``ref`` of /media/{id}/metadata: a backdrop, a face), fetched by Portalab
  const artwork = (ref, size) => ask({ type: "artwork", ref: String(ref), size: String(size || "w500") })
    .then(
    (answer) => URL.createObjectURL(new Blob([answer.buffer], { type: String(answer.mime || "") })),
  );
  const resize = () => send({ type: "resize", height: Math.ceil(document.documentElement.scrollHeight) });
  window.addEventListener("message", async (event) => {
    if (event.source !== host || !event.data || typeof event.data !== "object") return;
    const data = event.data;
    if (data.type === "answer") {
      const job = waiting.get(data.id);
      waiting.delete(data.id);
      if (!job) return;
      if (data.ok) job.resolve(data.value);
      else {
        const error = new Error(String((data.error && data.error.message) || "refused"));
        error.code = String((data.error && data.error.code) || "refused");
        job.reject(error);
      }
      return;
    }
    if (data.type === "live") {
      for (const listener of topics.get(data.topic) || []) {
        try { listener(data.data); } catch (error) { send({ type: "error", message: String(error) }); }
      }
      return;
    }
    if (data.type === "ping") { send({ type: "pong", n: data.n }); return; }
    if (data.type === "context") {
      context = data.context || {};
      applyTheme();
      for (const listener of listeners) {
        try { listener(context); } catch (error) { send({ type: "error", message: String(error) }); }
      }
      return;
    }
    if (data.type !== "run" || mounted) return;
    context = data.context || {};
    applyTheme();
    try {
      for (const font of Array.isArray(data.fonts) ? data.fonts : []) {
        try {
          const face = new FontFace(String(font.family), font.buffer, font.descriptors || {});
          document.fonts.add(await face.load());
        } catch (error) { /* a font that does not load: the next one in the list is used */ }
      }
      if (data.css) {
        const style = document.createElement("style");
        style.textContent = String(data.css);
        document.head.appendChild(style);
      }
      const url = URL.createObjectURL(new Blob([String(data.source)], { type: "text/javascript" }));
      const module = await import(url);
      URL.revokeObjectURL(url);
      if (typeof module.default !== "function") throw new Error("the view has no default export");
      const root = document.getElementById("root");
      const messages = () => (context.messages || {});
      const api = {
        get context() { return context; },
        get params() { return context.params || {}; },
        t: (key, values) => {
          let text = messages()[key] ?? key;
          for (const [name, value] of Object.entries(values || {})) {
            text = text.split("{" + name + "}").join(String(value));
          }
          return text;
        },
        call: (method, path, body, query) => ask({
          type: "call", method: String(method), path: String(path), body: body ?? null, query: query ?? null,
        }),
        get: (path, query) =>
          ask({ type: "call", method: "GET", path: String(path), body: null, query: query ?? null }),
        post: (path, body) =>
          ask({ type: "call", method: "POST", path: String(path), body: body ?? {}, query: null }),
        subscribe: (topic, listener) => {
          const name = String(topic);
          if (!topics.has(name)) { topics.set(name, new Set()); send({ type: "subscribe", topic: name }); }
          topics.get(name).add(listener);
          return () => topics.get(name)?.delete(listener);
        },
        asset,
        image,
        artwork,
        open: (surface, params) => send({ type: "open", surface: String(surface), params: params || {} }),
        close: () => send({ type: "close" }),
        navigate: (to) => send({ type: "navigate", to: String(to) }),
        resize,
        onContext: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
      };
      mounted = module.default(root, api) || null;
      new ResizeObserver(resize).observe(document.documentElement);
      resize();
      send({ type: "ready" });
    } catch (error) {
      send({ type: "error", message: String(error && error.message || error) });
    }
  });
  send({ type: "loaded" });
})();
"""

_HASH = base64.b64encode(hashlib.sha256(VIEW_BOOTSTRAP.encode()).digest()).decode()

VIEW_POLICY = (
    "default-src 'none'; "
    f"script-src 'sha256-{_HASH}' blob:; "
    "style-src 'unsafe-inline' blob:; "
    "img-src blob: data:; font-src blob: data:; media-src blob: data:; "
    "connect-src 'none'; worker-src 'none'; child-src 'none'; frame-src 'none'; object-src 'none'; "
    "manifest-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)

VIEW_DOCUMENT = (
    '<!doctype html><html><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    "<style>html,body{margin:0;background:transparent}#root{min-height:100%}</style></head>"
    f'<body><div id="root"></div><script>{VIEW_BOOTSTRAP}</script></body></html>'
)

VIEW_HEADERS = {
    "Content-Security-Policy": VIEW_POLICY,
    "X-Frame-Options": "SAMEORIGIN",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
}

# what a view's folder may hold, and how each is served (never as a page of Portalab's origin)
VIEW_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
}
VIEW_FILE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, no-cache",
}
