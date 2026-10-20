import { Fragment, type ReactNode } from "react";
import { Link } from "react-router";
import type { AiSource } from "../api";

/**
 * An answer's text, laid out (issue 171): paragraphs, lists, **bold**, *italics*, `code`, links to the
 * portal's own pages (``/…`` only — any other address stays text) and the ``[n]`` source numbers as links to
 * their source. Built as React elements from the text: nothing the model writes is ever read as HTML.
 */
// an address naming one item (an id): a link only when it is one of the answer's sources — never an item made up
const NAMES_ONE = /\/[0-9a-f]{8}-?[0-9a-f-]{4,}|\/\d{2,}(\/|$|\?)/i;
const INLINE = /(\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\s]+\)|\[\d{1,2}\]|`[^`\n]+`|\*[^*\n]+\*|_[^_\n]+_)/g;

function inline(text: string, sources: AiSource[], key: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    const at = `${key}-${index}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={at}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={at}>{part.slice(1, -1)}</code>;
    const cite = /^\[(\d{1,2})\]$/.exec(part);
    if (cite) {
      const source = sources.find((s) => s.n === Number(cite[1]));
      return source?.url?.startsWith("/") ? (
        <Link key={at} className="ai-cite" to={source.url} title={source.title}>
          {cite[1]}
        </Link>
      ) : source ? (
        <span key={at} className="ai-cite" title={source.title}>
          {cite[1]}
        </span>
      ) : null; // a number the answer made up: not shown
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      const [, label, href] = link;
      const known = !NAMES_ONE.test(href ?? "") || sources.some((s) => s.url === href);
      return href?.startsWith("/") && !href.startsWith("//") && known ? (
        <Link key={at} to={href}>
          {label}
        </Link>
      ) : (
        <Fragment key={at}>{label}</Fragment>
      );
    }
    if ((part.startsWith("*") && part.endsWith("*")) || (part.startsWith("_") && part.endsWith("_")))
      return part.length > 2 ? <em key={at}>{part.slice(1, -1)}</em> : part;
    return part;
  });
}

type Block = { kind: "p" | "ul" | "ol" | "h"; lines: string[] };

function blocks(text: string): Block[] {
  const out: Block[] = [];
  for (const raw of text.replace(/\r/g, "").split("\n")) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const number = /^\s*\d{1,2}[.)]\s+(.*)$/.exec(line);
    const heading = /^#{1,4}\s+(.*)$/.exec(line);
    const last = out[out.length - 1];
    if (!line.trim()) {
      out.push({ kind: "p", lines: [] });
    } else if (bullet) {
      if (last?.kind === "ul") last.lines.push(bullet[1] ?? "");
      else out.push({ kind: "ul", lines: [bullet[1] ?? ""] });
    } else if (number) {
      if (last?.kind === "ol") last.lines.push(number[1] ?? "");
      else out.push({ kind: "ol", lines: [number[1] ?? ""] });
    } else if (heading) {
      out.push({ kind: "h", lines: [heading[1] ?? ""] });
    } else if (last?.kind === "p" && last.lines.length) {
      last.lines.push(line);
    } else if ((last?.kind === "ul" || last?.kind === "ol") && /^\s{2,}/.test(raw)) {
      last.lines[last.lines.length - 1] += ` ${line.trim()}`; // a list item going on
    } else {
      out.push({ kind: "p", lines: [line] });
    }
  }
  return out.filter((b) => b.lines.length);
}

export function AnswerText({ text, sources = [] }: { text: string; sources?: AiSource[] }) {
  return (
    <div className="ai-answer">
      {blocks(text).map((block, index) => {
        const key = `b${index}`;
        if (block.kind === "ul" || block.kind === "ol") {
          const List = block.kind;
          return (
            <List key={key}>
              {block.lines.map((line, item) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: a list's items keep their order
                <li key={item}>{inline(line, sources, `${key}-${item}`)}</li>
              ))}
            </List>
          );
        }
        if (block.kind === "h")
          return (
            <p key={key} className="ai-answer__heading">
              {inline(block.lines[0] ?? "", sources, key)}
            </p>
          );
        return (
          <p key={key}>
            {block.lines.map((line, row) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a paragraph's lines keep their order
              <Fragment key={row}>
                {row ? <br /> : null}
                {inline(line, sources, `${key}-${row}`)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
