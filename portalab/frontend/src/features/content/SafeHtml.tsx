import { type MouseEvent, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import { type ResolvedLink, useResolvedLinks } from "./api";
import "./content.css";

/**
 * Sanitized content (spec 011 T008): the HTML comes from the server's single sanitizer (raw HTML off,
 * allowlist) and is inserted as-is; portal links (``portalab://``) are resolved **per viewer** after
 * rendering — a forbidden target never shows its title, archived/deleted targets degrade with a text label
 * (never a dead end); Mermaid placeholders are rendered client-side in strict mode, falling back to code.
 */
const REF = /data-ref="(portalab:\/\/[^"]+)"/g;

function refsOf(html: string): string[] {
  return [...new Set([...html.matchAll(REF)].map((m) => m[1] as string))];
}

export function annotateLinks(
  root: HTMLElement,
  states: ResolvedLink[],
  labels: Record<string, string>,
): void {
  const byRef = new Map(states.map((s) => [s.ref, s]));
  for (const anchor of root.querySelectorAll<HTMLAnchorElement>("a[data-ref]")) {
    const resolved = byRef.get(anchor.dataset.ref ?? "");
    if (!resolved) continue;
    anchor.dataset.state = resolved.state;
    anchor.querySelector(".content-ref__state")?.remove();
    if ((resolved.state === "ok" || resolved.state === "archived") && resolved.url) {
      anchor.setAttribute("href", resolved.url);
      anchor.dataset.internal = "true";
      if (resolved.title) anchor.setAttribute("title", resolved.title);
    } else {
      anchor.removeAttribute("href");
      anchor.removeAttribute("title");
      anchor.setAttribute("aria-disabled", "true");
    }
    if (resolved.state !== "ok") {
      const label = document.createElement("span");
      label.className = "content-ref__state";
      label.textContent = ` (${labels[resolved.state] ?? resolved.state})`;
      anchor.append(label);
    }
  }
}

let mermaidCounter = 0;

async function renderDiagrams(root: HTMLElement, label: string): Promise<void> {
  const blocks = [...root.querySelectorAll<HTMLElement>("pre[data-mermaid]")];
  if (!blocks.length) return;
  const { default: mermaid } = await import("mermaid");
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", flowchart: { htmlLabels: false } });
  for (const block of blocks) {
    const source = block.textContent ?? "";
    try {
      mermaidCounter += 1;
      const { svg } = await mermaid.render(`mermaid-${mermaidCounter}`, source);
      const figure = document.createElement("figure");
      figure.className = "content-diagram";
      figure.setAttribute("role", "img");
      figure.setAttribute("aria-label", label);
      figure.innerHTML = svg; // produced by Mermaid in strict mode (sanitized, no HTML labels)
      block.replaceWith(figure);
    } catch {
      block.dataset.mermaidFailed = "true"; // the source stays visible as code
    }
  }
}

export function SafeHtml({ html, diagrams = true }: { html: string; diagrams?: boolean }) {
  const t = useT();
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  const refs = useMemo(() => refsOf(html), [html]);
  const links = useResolvedLinks(refs);
  const labels = useMemo(
    () => ({
      forbidden: t("content:link.forbidden"),
      archived: t("content:link.archived"),
      deleted: t("content:link.deleted"),
      unavailable: t("content:link.unavailable"),
    }),
    [t],
  );
  useEffect(() => {
    if (ref.current && links.data) annotateLinks(ref.current, links.data, labels);
  }, [links.data, labels]);
  // biome-ignore lint/correctness/useExhaustiveDependencies: the DOM to scan changes with ``html``
  useEffect(() => {
    if (ref.current && diagrams && ref.current.querySelector("pre[data-mermaid]"))
      void renderDiagrams(ref.current, t("content:diagram"));
  }, [html, diagrams, t]);
  // callout titles come in English from the renderer: shown in the reader's language
  // biome-ignore lint/correctness/useExhaustiveDependencies: the DOM to scan changes with ``html``
  useEffect(() => {
    for (const title of ref.current?.querySelectorAll<HTMLElement>("[data-callout] > .callout-title") ?? []) {
      const kind = title.parentElement?.dataset.callout;
      if (kind) title.textContent = t(`content:callout.${kind}`);
    }
  }, [html, t]);
  // issue 239: a page's image (a guide's annotated screenshot) opens full size — on a phone it is shown small
  // biome-ignore lint/correctness/useExhaustiveDependencies: the DOM to scan changes with ``html``
  useEffect(() => {
    for (const image of ref.current?.querySelectorAll<HTMLImageElement>("img[data-asset]") ?? []) {
      if (image.closest("a")) continue;
      const link = document.createElement("a");
      link.className = "content-image";
      link.href = image.getAttribute("src") ?? "";
      link.target = "_blank";
      link.rel = "noopener";
      link.setAttribute("aria-label", t("content:image.open", { alt: image.alt }));
      image.replaceWith(link);
      link.append(image);
    }
  }, [html, t]);
  const onClick = (event: MouseEvent<HTMLDivElement>) => {
    const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[data-internal]");
    const href = anchor?.getAttribute("href");
    if (anchor && href?.startsWith("/") && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      navigate(href);
    }
  };
  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents lint/a11y/noStaticElementInteractions: delegates real link activation (links are keyboard-operable themselves)
    <div
      ref={ref}
      className="content-body"
      onClick={onClick}
      // biome-ignore lint/security/noDangerouslySetInnerHtml: server-sanitized by the single Markdown pipeline (nh3 allowlist)
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
