"""The sandbox a pack's script runs in (issue 1): a page of its own, framed by the interface with
``sandbox="allow-scripts"`` and nothing else — an opaque origin, so no cookie, no session, no storage of
Portalab's, no request it would accept; no form, no popup, no navigation of the page around it.

Its own content security policy closes the rest: no network at all (``connect-src 'none'``), no image,
font or media but the ones it is handed (``blob:``/``data:``), no script but its own bootstrap (by its hash)
and the pack's module, handed to it as text by the interface and imported from a ``blob:`` URL. It may only
be framed by Portalab itself.

The bootstrap speaks to the interface by messages only, from and to the window that framed it:

- in: ``{type: "run", source, element, context}`` — the module's code and what it may know (a navigation:
  the sections and pages the member may open, the current page, the interface's colours and words);
  ``{type: "context", context}`` — that knowledge changed (another page);
  ``{type: "asset", id, buffer, mime, error}`` — a file of its own element it asked for (its bytes: it makes
  its own ``blob:`` URL);
- in: ``{type: "ping", n}`` every few seconds once it is ready — it answers ``pong`` (028: a script that
  stops answering is stopped, its default takes over);
- out: ``ready``, ``error``, ``asset`` (a file of its own element, by relative path), and for a navigation
  ``navigate`` (a page's key among those it was given — the interface checks it), ``expand`` (cover the screen
  while open). A widget is placed and resized by the member within the sizes its element declares.
"""

import base64
import hashlib

BOOTSTRAP = r"""
"use strict";
(() => {
  const host = window.parent;
  let mounted = null;
  let pending = 0;
  const waiting = new Map();
  const listeners = new Set();
  let context = {};
  const send = (message) => host.postMessage(message, "*");
  const asset = (path) => new Promise((resolve, reject) => {
    const id = ++pending;
    waiting.set(id, { resolve, reject });
    send({ type: "asset", id, path: String(path) });
  });
  window.addEventListener("message", async (event) => {
    if (event.source !== host || !event.data || typeof event.data !== "object") return;
    const data = event.data;
    if (data.type === "asset") {
      const job = waiting.get(data.id);
      waiting.delete(data.id);
      if (!job) return;
      if (data.buffer instanceof ArrayBuffer) {
        job.resolve(URL.createObjectURL(new Blob([data.buffer], { type: String(data.mime || "") })));
      } else {
        job.reject(new Error(data.error || "not found"));
      }
      return;
    }
    if (data.type === "ping") {
      send({ type: "pong", n: data.n });
      return;
    }
    if (data.type === "context") {
      context = data.context || {};
      for (const listener of listeners) {
        try { listener(context); } catch (error) { send({ type: "error", message: String(error) }); }
      }
      return;
    }
    if (data.type !== "run" || mounted) return;
    context = data.context || {};
    try {
      const url = URL.createObjectURL(new Blob([String(data.source)], { type: "text/javascript" }));
      const module = await import(url);
      URL.revokeObjectURL(url);
      if (typeof module.default !== "function") throw new Error("the module has no default export");
      const root = document.getElementById("root");
      const api = {
        ...context,
        get context() { return context; },
        asset,
        onContext: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
        navigate: (key) => send({ type: "navigate", key: String(key) }),
        expand: (open) => send({ type: "expand", open: Boolean(open) }),
      };
      mounted = module.default(root, api) || null;
      send({ type: "ready" });
    } catch (error) {
      send({ type: "error", message: String(error && error.message || error) });
    }
  });
  send({ type: "loaded" });
})();
"""

_HASH = base64.b64encode(hashlib.sha256(BOOTSTRAP.encode()).digest()).decode()

POLICY = (
    "default-src 'none'; "
    f"script-src 'sha256-{_HASH}' blob:; "
    "style-src 'unsafe-inline' blob:; "
    "img-src blob: data:; font-src blob: data:; media-src blob: data:; "
    "connect-src 'none'; worker-src 'none'; child-src 'none'; frame-src 'none'; object-src 'none'; "
    "manifest-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)

DOCUMENT = (
    '<!doctype html><html><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    "<style>html,body{margin:0;height:100%;background:transparent;overflow:hidden}"
    "#root{position:fixed;inset:0}</style></head>"
    f'<body><div id="root"></div><script>{BOOTSTRAP}</script></body></html>'
)

HEADERS = {
    "Content-Security-Policy": POLICY,
    "X-Frame-Options": "SAMEORIGIN",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
}
