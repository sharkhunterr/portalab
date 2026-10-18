import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { connectStream } from "../../../api/stream";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextAreaField, TextField } from "../../../design-system/components/Field";
import { type Column, Table } from "../../../design-system/components/Layout";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { SafeHtml } from "../../content/SafeHtml";
import { Cancelled, usePluginAction } from "./PluginConfirm";
import { Surface } from "./Surface";

/**
 * 030: a plugin's declarative blocks, drawn by Portalab's components wherever they appear — a page, a modal or
 * a drawer opened by a slot. ``params`` are what the place gives (the page's address, the title of a media
 * page…): they go to the blocks' data routes and with their forms and actions.
 */

interface FieldSpec {
  type?: string;
  maxLength?: number;
  title?: string;
  format?: string;
}

export interface Block {
  kind:
    | "markdown"
    | "stat"
    | "list"
    | "table"
    | "chart"
    | "form"
    | "thread"
    | "cards"
    | "checklist"
    | "actions";
  live?: string;
  buttons?: Array<{ label_key: string; opens?: string; action?: string; then?: string }>;
  html?: string;
  title_key?: string;
  data?: string;
  columns?: string[];
  schema?: { properties?: Record<string, FieldSpec>; required?: string[]; order?: string[] };
  action?: string;
  submit_key?: string;
}

type Item = Record<string, unknown>;

/** Plugin data routes answer with a typed state and data (spec 023 R12). */
interface DataState {
  state?: string;
  value?: number;
  label?: string;
  title?: string;
  items?: Item[];
  message?: string;
  link?: string;
}

const STATES = new Set(["available", "partial", "stale", "unavailable", "error", "no-data", "unauthorized"]);

/** A link a plugin gives is one of its own pages only (030): never another place, never another site. */
export function ownLink(plugin: string, link: unknown): string | null {
  if (typeof link !== "string" || link.includes("//") || link.includes("..")) return null;
  if (link.startsWith(`/plugins/${plugin}/`)) return link;
  return /^\/media\/[A-Za-z0-9_-]{1,80}$/.test(link) ? link : null; // a title's own page
}

async function pluginGet(plugin: string, path: string, params: Record<string, string>): Promise<DataState> {
  // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
  const result = await api.GET(
    `/api/v1/plugins/${plugin}/${path}` as any,
    { params: { query: params } } as any,
  );
  return (result.data ?? {}) as DataState;
}

/** The address's parameters of a plugin page (``?topic=12``), bounded. */
export function usePageParams(): Record<string, string> {
  const [search] = useSearchParams();
  return Object.fromEntries([...search.entries()].map(([k, v]) => [k, v.slice(0, 200)]));
}

function ListItems({ plugin, items }: { plugin: string; items: Item[] }) {
  return (
    <ul className="ds-stack">
      {items.map((item, index) => {
        const label = String(item.label ?? item.title ?? "");
        const link = ownLink(plugin, item.link);
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: plugin rows carry no stable id
          <li key={index}>
            {link ? <Link to={link}>{label}</Link> : label}
            {item.meta ? <span className="ds-page-header__context"> · {String(item.meta)}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

function Thread({ items }: { items: Item[] }) {
  const t = useT();
  const format = useFormat();
  return (
    <ol className="ds-stack plugin-thread">
      {items.map((item, index) => (
        <li key={String(item.id ?? index)} className="ds-card">
          <p>
            <strong>{String(item.author ?? "")}</strong>
            {typeof item.at === "string" ? (
              <span className="ds-page-header__context"> · {format.dateTime(item.at)}</span>
            ) : null}
          </p>
          {item.removed ? (
            <p>{t("plugins:block.removed")}</p>
          ) : (
            <p className="plugin-thread__body">{String(item.body ?? "")}</p>
          )}
        </li>
      ))}
    </ol>
  );
}

function Cards({ plugin, items }: { plugin: string; items: Item[] }) {
  return (
    <div className="ds-grid">
      {items.map((item, index) => {
        const link = ownLink(plugin, item.link);
        const title = String(item.title ?? item.label ?? "");
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: plugin rows carry no stable id
          <article key={index} className="ds-card ds-stack">
            <h3>{link ? <Link to={link}>{title}</Link> : title}</h3>
            {item.subtitle ? <p>{String(item.subtitle)}</p> : null}
          </article>
        );
      })}
    </div>
  );
}

function useLive(plugin: string, topic: string | undefined, refetch: () => unknown) {
  useEffect(() => {
    if (!topic) return undefined;
    const handle = connectStream({ topics: [`plugin.${plugin}.${topic}`], onEvent: () => void refetch() });
    return () => handle.close();
  }, [plugin, topic, refetch]);
}

function Checklist({ plugin, block, params, items }: BlockProps & { items: Item[] }) {
  const queries = useQueryClient();
  const action = usePluginAction(plugin);
  const toggle = useMutation({
    mutationFn: (input: { id: unknown; checked: boolean }) =>
      action.run(block.action ?? "", { ...params, id: input.id, checked: input.checked }),
    onSettled: () => queries.invalidateQueries({ queryKey: ["plugin-data", plugin] }),
  });
  return (
    <ul className="ds-stack">
      {items.map((item, index) => (
        <li key={String(item.id ?? index)}>
          <CheckboxField
            label={String(item.label ?? "")}
            checked={Boolean(item.checked)}
            disabled={toggle.isPending}
            onChange={(e) => toggle.mutate({ id: item.id, checked: e.target.checked })}
          />
        </li>
      ))}
      {action.dialog}
    </ul>
  );
}

function DataBlock({ plugin, block, params }: BlockProps) {
  const t = useT();
  const format = useFormat();
  const query = useQuery({
    queryKey: ["plugin-data", plugin, block.data, params],
    queryFn: () => pluginGet(plugin, block.data ?? "", params),
  });
  useLive(plugin, block.live, query.refetch);
  const title = query.data?.title ?? (block.title_key ? t(block.title_key) : "");
  const state = query.data?.state && STATES.has(query.data.state) ? query.data.state : null;
  const items = query.data?.items ?? [];
  return (
    <section aria-label={title} className="ds-card ds-stack">
      <h2>{title}</h2>
      {query.isError ? <FunctionalState state="unavailable" onRetry={() => query.refetch()} /> : null}
      {state && state !== "available" ? <FunctionalState state={state as "no-data"} /> : null}
      {query.data && block.kind === "stat" ? (
        <p className="gamification-values">
          <strong>{format.number(Number(query.data.value ?? 0))}</strong> {query.data.label ?? ""}
        </p>
      ) : null}
      {query.data && block.kind === "list" ? <ListItems plugin={plugin} items={items} /> : null}
      {query.data && block.kind === "thread" ? <Thread items={items} /> : null}
      {query.data && block.kind === "cards" ? <Cards plugin={plugin} items={items} /> : null}
      {query.data && block.kind === "checklist" ? (
        <Checklist plugin={plugin} block={block} params={params} items={items} />
      ) : null}
      {query.data && (block.kind === "table" || block.kind === "chart") ? (
        <Table
          caption={title}
          columns={(block.columns ?? []).map(
            (column): Column<Item> => ({
              key: column,
              header: column,
              render: (row) => String(row[column] ?? ""),
            }),
          )}
          rows={items}
          rowKey={(row) => JSON.stringify(row)}
        />
      ) : null}
    </section>
  );
}

function FormBlock({ plugin, block, params, onDone }: BlockProps) {
  const t = useT();
  const navigate = useNavigate();
  const queries = useQueryClient();
  const action = usePluginAction(plugin);
  // 030: a form that edits starts from the current values (its ``data`` route answers ``{values}``)
  const current = useQuery({
    queryKey: ["plugin-data", plugin, block.data, params, "values"],
    enabled: Boolean(block.data),
    queryFn: () => pluginGet(plugin, block.data ?? "", params),
  });
  // the server keeps a schema's properties without their order: ``order`` (or ``required``) gives it back
  const rank = block.schema?.order ?? block.schema?.required ?? [];
  const fields = Object.entries(block.schema?.properties ?? {}).sort(([a], [b]) => {
    const [x, y] = [rank.indexOf(a), rank.indexOf(b)];
    return (x < 0 ? rank.length : x) - (y < 0 ? rank.length : y);
  });
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const initial = (current.data as { values?: Record<string, string | boolean> } | undefined)?.values;
    if (!filled && initial) {
      setValues(initial);
      setFilled(true);
    }
  }, [current.data, filled]);
  const submit = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = { ...params }; // the page's own parameters (e.g. its topic)
      for (const [name, spec] of fields) {
        body[name] =
          spec.type === "number" || spec.type === "integer"
            ? Number(values[name] ?? 0)
            : (values[name] ?? "");
      }
      return (await action.run(block.action ?? "", body)) as DataState;
    },
    onSuccess: async (data) => {
      if (data?.state === "error") return;
      if (!block.data) setValues({});
      await queries.invalidateQueries({ queryKey: ["plugin-data", plugin] });
      const link = ownLink(plugin, data?.link);
      if (link) navigate(link);
      onDone?.();
    },
  });
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit.mutate();
  };
  const title = block.title_key ? t(block.title_key) : "";
  const cancelled = submit.error instanceof Cancelled;
  return (
    <form className="ds-card ds-stack" aria-label={title} onSubmit={onSubmit}>
      <h2>{title}</h2>
      {fields.map(([name, spec]) => {
        const label = spec.title ? t(spec.title) : name;
        if (spec.type === "boolean") {
          return (
            <CheckboxField
              key={name}
              label={label}
              checked={Boolean(values[name])}
              onChange={(e) => setValues({ ...values, [name]: e.target.checked })}
            />
          );
        }
        if (spec.format === "textarea") {
          return (
            <TextAreaField
              key={name}
              label={label}
              maxLength={spec.maxLength}
              required={(block.schema?.required ?? []).includes(name)}
              value={String(values[name] ?? "")}
              onChange={(e) => setValues({ ...values, [name]: e.target.value })}
            />
          );
        }
        return (
          <TextField
            key={name}
            label={label}
            type={spec.type === "number" || spec.type === "integer" ? "number" : "text"}
            maxLength={spec.maxLength}
            required={(block.schema?.required ?? []).includes(name)}
            value={String(values[name] ?? "")}
            onChange={(e) => setValues({ ...values, [name]: e.target.value })}
          />
        );
      })}
      {submit.isSuccess && submit.data?.message ? (
        <p role={submit.data.state === "error" ? "alert" : "status"}>{submit.data.message}</p>
      ) : null}
      {submit.isError && !cancelled ? <FunctionalState state="error" /> : null}
      <Button type="submit" disabled={submit.isPending}>
        {t(block.submit_key ?? "plugins:page.submit")}
      </Button>
      {action.dialog}
    </form>
  );
}

interface BlockProps {
  plugin: string;
  block: Block;
  params: Record<string, string>;
  onDone?: (() => void) | undefined;
}

function Actions({ plugin, block, params }: BlockProps) {
  const t = useT();
  const navigate = useNavigate();
  const action = usePluginAction(plugin);
  const [open, setOpen] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const run = async (button: NonNullable<Block["buttons"]>[number]) => {
    setFailed(false);
    if (button.opens) {
      setOpen(button.opens);
      return;
    }
    try {
      const data = (await action.run(button.action ?? "", { ...params })) as DataState;
      const link = ownLink(plugin, data?.link) ?? ownLink(plugin, button.then);
      if (link) navigate(link);
    } catch (error) {
      if (!(error instanceof Cancelled)) setFailed(true);
    }
  };
  return (
    <div className="ds-stack--row">
      {(block.buttons ?? []).map((button) => (
        <Button
          key={button.label_key}
          variant={button.opens ? "secondary" : "ghost"}
          onClick={() => run(button)}
        >
          {t(button.label_key)}
        </Button>
      ))}
      {failed ? <p role="alert">{t("plugins:block.failed")}</p> : null}
      {open ? <Surface plugin={plugin} surface={open} params={params} onClose={() => setOpen(null)} /> : null}
      {action.dialog}
    </div>
  );
}

/** A plugin's blocks, in order. */
export function PluginBlocks({
  plugin,
  blocks,
  params,
  onDone,
}: {
  plugin: string;
  blocks: Block[];
  params: Record<string, string>;
  onDone?: (() => void) | undefined;
}) {
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${block.kind}-${index}`;
        if (block.kind === "markdown") return <SafeHtml key={key} html={block.html ?? ""} diagrams={false} />;
        if (block.kind === "form")
          return <FormBlock key={key} plugin={plugin} block={block} params={params} onDone={onDone} />;
        if (block.kind === "actions")
          return <Actions key={key} plugin={plugin} block={block} params={params} />;
        return <DataBlock key={key} plugin={plugin} block={block} params={params} />;
      })}
    </>
  );
}
