import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { usePreview, useUploadAsset } from "./api";
import { SafeHtml } from "./SafeHtml";

/**
 * Markdown editor (spec 011 T012; #48): a toolbar that writes the Markdown for you (headings, bold,
 * italic, strikethrough, links, quotes, lists, checklists, code, tables, a separator, images), keyboard
 * shortcuts (Ctrl/⌘ B, I, K), a button group « Write · Side by side · Preview » and a word count. The
 * preview is produced by the **same server pipeline and sanitizer** as saved content (preview parity);
 * images are uploaded to the owning page/article.
 */
type Mode = "write" | "split" | "preview";

interface Tool {
  key: string;
  icon: string;
  /** Wraps the selection (or a placeholder) — or prefixes each selected line when ``line`` is set. */
  before: string;
  after?: string;
  line?: boolean;
  placeholder?: string;
  shortcut?: string;
}

const TOOLS: ReadonlyArray<Tool | "|"> = [
  { key: "heading2", icon: "lines", before: "## ", line: true, placeholder: "Title" },
  { key: "heading3", icon: "lines", before: "### ", line: true, placeholder: "Subtitle" },
  "|",
  { key: "bold", icon: "bold", before: "**", after: "**", placeholder: "bold", shortcut: "b" },
  { key: "italic", icon: "italic", before: "_", after: "_", placeholder: "italic", shortcut: "i" },
  { key: "strike", icon: "strike", before: "~~", after: "~~", placeholder: "text" },
  { key: "code", icon: "code", before: "`", after: "`", placeholder: "code" },
  "|",
  { key: "link", icon: "link", before: "[", after: "](https://)", placeholder: "link", shortcut: "k" },
  { key: "quote", icon: "message", before: "> ", line: true, placeholder: "Quote" },
  { key: "bullets", icon: "list", before: "- ", line: true, placeholder: "Item" },
  { key: "numbers", icon: "list", before: "1. ", line: true, placeholder: "Item" },
  { key: "tasks", icon: "check", before: "- [ ] ", line: true, placeholder: "To do" },
  "|",
  {
    key: "table",
    icon: "apps",
    before: "\n| Column | Column |\n| --- | --- |\n| ",
    after: " | |\n",
    placeholder: "Cell",
  },
  { key: "codeblock", icon: "terminal", before: "\n```\n", after: "\n```\n", placeholder: "code" },
  { key: "rule", icon: "minus", before: "\n---\n", placeholder: "" },
];

/** Applies a tool to the text around the selection; returns the new text and the new selection. */
export function applyTool(
  text: string,
  start: number,
  end: number,
  tool: Tool,
): { text: string; start: number; end: number } {
  const selected = text.slice(start, end);
  if (tool.line) {
    const from = text.lastIndexOf("\n", start - 1) + 1;
    const block = text.slice(from, end) || tool.placeholder || "";
    const lines = block.split("\n").map((line, index) => {
      const prefix = tool.key === "numbers" ? `${index + 1}. ` : tool.before;
      return line.startsWith(prefix) ? line.slice(prefix.length) : prefix + line; // a second click undoes it
    });
    const replaced = lines.join("\n");
    return {
      text: text.slice(0, from) + replaced + text.slice(end),
      start: from,
      end: from + replaced.length,
    };
  }
  const inner = selected || tool.placeholder || "";
  const after = tool.after ?? "";
  const next = text.slice(0, start) + tool.before + inner + after + text.slice(end);
  return { text: next, start: start + tool.before.length, end: start + tool.before.length + inner.length };
}

export function MarkdownEditor({
  value,
  onChange,
  ownerRef,
  label,
  rows = 18,
}: {
  value: string;
  onChange: (value: string) => void;
  ownerRef?: string | undefined;
  label: string;
  rows?: number;
}) {
  const t = useT();
  const id = useId();
  const [mode, setMode] = useState<Mode>("write");
  const [debounced, setDebounced] = useState(value);
  const area = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), 400);
    return () => clearTimeout(timer);
  }, [value]);
  const preview = usePreview(mode === "write" ? "" : debounced);
  const upload = useUploadAsset(ownerRef ?? "");

  const insert = (tool: Tool) => {
    const el = area.current;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    const next = applyTool(value, start, end, tool);
    onChange(next.text);
    requestAnimationFrame(() => {
      if (!area.current) return;
      area.current.focus();
      area.current.setSelectionRange(next.start, next.end);
    });
  };
  const onFile = (file: File | undefined) => {
    if (!file || !ownerRef) return;
    upload.mutate(file, {
      onSuccess: (asset) => {
        if (asset) insert({ key: "image", icon: "image", before: `\n${asset.markdown}\n`, placeholder: "" });
      },
    });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    const tool = TOOLS.find((x): x is Tool => x !== "|" && x.shortcut === event.key.toLowerCase());
    if (!tool) return;
    event.preventDefault();
    insert(tool);
  };
  const words = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <div className="markdown-editor" data-mode={mode}>
      <div className="markdown-editor__bar">
        <label htmlFor={id} className="markdown-editor__label">
          {label}
        </label>
        <fieldset className="markdown-editor__modes">
          <legend className="visually-hidden">{t("content:editor.mode")}</legend>
          {(["write", "split", "preview"] as const).map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={mode === key}
              data-mode={key}
              onClick={() => setMode(key)}
            >
              <Icon name={key === "write" ? "feather" : key === "split" ? "layers" : "eye"} size={15} />
              {t(`content:editor.${key}`)}
            </button>
          ))}
        </fieldset>
      </div>
      {mode !== "preview" ? (
        <div className="markdown-editor__tools" role="toolbar" aria-label={t("content:editor.tools")}>
          {TOOLS.map((tool, index) =>
            tool === "|" ? (
              // biome-ignore lint/suspicious/noArrayIndexKey: separators have no identity
              <span key={`sep-${index}`} className="markdown-editor__sep" aria-hidden="true" />
            ) : (
              <button
                key={tool.key}
                type="button"
                className="markdown-editor__tool"
                onClick={() => insert(tool)}
                aria-label={t(`content:editor.tool.${tool.key}`)}
                title={`${t(`content:editor.tool.${tool.key}`)}${tool.shortcut ? ` (Ctrl+${tool.shortcut.toUpperCase()})` : ""}`}
              >
                <ToolGlyph tool={tool} />
              </button>
            ),
          )}
          {ownerRef ? (
            <>
              <span className="markdown-editor__sep" aria-hidden="true" />
              <button
                type="button"
                className="markdown-editor__tool"
                onClick={() => fileRef.current?.click()}
                disabled={upload.isPending}
                aria-label={t("content:editor.image")}
                title={t("content:editor.image")}
              >
                <Icon name={upload.isPending ? "spinner" : "image"} size={16} />
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                hidden
                onChange={(event) => onFile(event.currentTarget.files?.[0])}
              />
            </>
          ) : null}
        </div>
      ) : null}
      <div className="markdown-editor__panes">
        {mode !== "preview" ? (
          <textarea
            ref={area}
            id={id}
            className="markdown-editor__input"
            value={value}
            rows={rows}
            placeholder={t("content:editor.placeholder")}
            onKeyDown={onKeyDown}
            onChange={(e) => onChange(e.target.value)}
          />
        ) : null}
        {mode !== "write" ? (
          <section aria-label={t("content:editor.preview")} className="markdown-editor__preview content-body">
            {preview.data ? (
              <SafeHtml html={preview.data.html} diagrams />
            ) : (
              <p className="markdown-editor__empty">{t("content:editor.previewEmpty")}</p>
            )}
            {preview.data?.warnings.includes("possible_secret") ? (
              <p role="status">{t("content:editor.sensitiveWarning")}</p>
            ) : null}
          </section>
        ) : null}
      </div>
      <p className="markdown-editor__foot">
        <span>{t("content:editor.words", { count: words })}</span>
        <span>{t("content:editor.markdown")}</span>
      </p>
      {upload.isError ? <p role="alert">{t("content:editor.uploadFailed")}</p> : null}
    </div>
  );
}

/** A tool's face: letters where they say it best (H2, B, I, S), an icon otherwise. */
function ToolGlyph({ tool }: { tool: Tool }) {
  const letters: Record<string, string> = {
    heading2: "H2",
    heading3: "H3",
    bold: "B",
    italic: "I",
    strike: "S",
    numbers: "1.",
  };
  const text = letters[tool.key];
  if (text)
    return (
      <span className="markdown-editor__glyph" data-tool={tool.key}>
        {text}
      </span>
    );
  return <Icon name={tool.icon} size={16} />;
}
