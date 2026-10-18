import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextAreaField, TextField } from "../../../design-system/components/Field";
import { type Column, Table } from "../../../design-system/components/Layout";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { SafeHtml } from "../../content/SafeHtml";
import { Cancelled, usePluginAction } from "./PluginConfirm";

interface FieldSpec {
  type?: string;
  maxLength?: number;
  title?: string;
  format?: string;
}

interface Block {
  kind: "markdown" | "stat" | "list" | "table" | "chart" | "form" | "thread" | "cards";
  html?: string;
  title_key?: string;
  data?: string;
  columns?: string[];
  schema?: { properties?: Record<string, FieldSpec>; required?: string[]; order?: string[] };
  action?: string;
  submit_key?: string;
}

interface Page {
  plugin: string;
  key: string;
  title_key: string;
  blocks: Block[];
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
  if (typeof link !== "string") return null;
  const prefix = `/plugins/${plugin}/`;
  return link.startsWith(prefix) && !link.includes("//") && !link.includes("..") ? link : null;
}

async function pluginGet(plugin: string, path: string, params: Record<string, string>): Promise<DataState> {
  // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
  const result = await api.GET(
    `/api/v1/plugins/${plugin}/${path}` as any,
    { params: { query: params } } as any,
  );
  return (result.data ?? {}) as DataState;
}

function usePageParams(): Record<string, string> {
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

function DataBlock({ plugin, block }: { plugin: string; block: Block }) {
  const t = useT();
  const format = useFormat();
  const params = usePageParams();
  const query = useQuery({
    queryKey: ["plugin-data", plugin, block.data, params],
    queryFn: () => pluginGet(plugin, block.data ?? "", params),
  });
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

function FormBlock({ plugin, block }: { plugin: string; block: Block }) {
  const t = useT();
  const navigate = useNavigate();
  const queries = useQueryClient();
  const params = usePageParams();
  const action = usePluginAction(plugin);
  // the server keeps a schema's properties without their order: ``order`` (or ``required``) gives it back
  const rank = block.schema?.order ?? block.schema?.required ?? [];
  const fields = Object.entries(block.schema?.properties ?? {}).sort(([a], [b]) => {
    const [x, y] = [rank.indexOf(a), rank.indexOf(b)];
    return (x < 0 ? rank.length : x) - (y < 0 ? rank.length : y);
  });
  const [values, setValues] = useState<Record<string, string | boolean>>({});
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
      setValues({});
      await queries.invalidateQueries({ queryKey: ["plugin-data", plugin] });
      const link = ownLink(plugin, data?.link);
      if (link) navigate(link);
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
      {submit.isSuccess && submit.data?.message ? <p role="status">{submit.data.message}</p> : null}
      {submit.isError && !cancelled ? <FunctionalState state="error" /> : null}
      <Button type="submit" disabled={submit.isPending}>
        {t(block.submit_key ?? "plugins:page.submit")}
      </Button>
      {action.dialog}
    </form>
  );
}

/**
 * ``/plugins/:pluginKey/:pageKey`` (spec 023 T032, 030): a plugin page rendered from its declarative blocks
 * with design-system components only — sanitized Markdown (011), data blocks with functional states (lists,
 * tables, threads, cards), forms from a JSON Schema posting to the plugin's own action, a committing action
 * confirmed in Portalab's own dialog. No plugin JavaScript is ever executed.
 */
export default function PageRenderer() {
  const t = useT();
  const { pluginKey = "", pageKey = "" } = useParams();
  const page = useQuery({
    queryKey: ["plugin-page", pluginKey, pageKey],
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/plugins/{key}/pages/{page}", {
          params: { path: { key: pluginKey, page: pageKey } },
        })
      ).data as unknown as Page,
  });
  if (page.isPending) return <FunctionalState state="loading" />;
  if (page.isError || !page.data) {
    return (
      <div className="ds-stack">
        <FunctionalState state="unavailable" label={t("plugins:page.unavailable")} />
        <Link to="/">{t("plugins:page.home")}</Link>
      </div>
    );
  }
  return (
    <div className="ds-stack">
      <PageHeader icon="plug" title={t(page.data.title_key)} />
      {page.data.blocks.map((block, index) => {
        const key = `${block.kind}-${index}`;
        if (block.kind === "markdown") return <SafeHtml key={key} html={block.html ?? ""} diagrams={false} />;
        if (block.kind === "form") return <FormBlock key={key} plugin={pluginKey} block={block} />;
        return <DataBlock key={key} plugin={pluginKey} block={block} />;
      })}
    </div>
  );
}
