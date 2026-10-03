import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { type Column, Table } from "../../../design-system/components/Layout";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { SafeHtml } from "../../content/SafeHtml";

interface Block {
  kind: "markdown" | "stat" | "list" | "table" | "chart" | "form";
  html?: string;
  title_key?: string;
  data?: string;
  columns?: string[];
  schema?: { properties?: Record<string, { type?: string; maxLength?: number }>; required?: string[] };
  action?: string;
  submit_key?: string;
}

interface Page {
  plugin: string;
  key: string;
  title_key: string;
  blocks: Block[];
}

/** Plugin data routes answer with a typed state and data (spec 023 R12). */
interface DataState {
  state?: string;
  value?: number;
  label?: string;
  items?: Array<Record<string, unknown>>;
  message?: string;
}

const STATES = new Set(["available", "partial", "stale", "unavailable", "error", "no-data", "unauthorized"]);

async function pluginGet(plugin: string, path: string): Promise<DataState> {
  // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
  const result = await api.GET(`/api/v1/plugins/${plugin}/${path}` as any, {});
  return (result.data ?? {}) as DataState;
}

function DataBlock({ plugin, block }: { plugin: string; block: Block }) {
  const t = useT();
  const format = useFormat();
  const query = useQuery({
    queryKey: ["plugin-data", plugin, block.data],
    queryFn: () => pluginGet(plugin, block.data ?? ""),
  });
  const title = block.title_key ? t(block.title_key) : "";
  const state = query.data?.state && STATES.has(query.data.state) ? query.data.state : null;
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
      {query.data && block.kind === "list" ? (
        <ul>
          {(query.data.items ?? []).map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: plugin rows carry no stable id
            <li key={index}>{String(item.label ?? item.title ?? "")}</li>
          ))}
        </ul>
      ) : null}
      {query.data && (block.kind === "table" || block.kind === "chart") ? (
        <Table
          caption={title}
          columns={(block.columns ?? []).map(
            (column): Column<Record<string, unknown>> => ({
              key: column,
              header: column,
              render: (row) => String(row[column] ?? ""),
            }),
          )}
          rows={query.data.items ?? []}
          rowKey={(row) => JSON.stringify(row)}
        />
      ) : null}
    </section>
  );
}

function FormBlock({ plugin, block }: { plugin: string; block: Block }) {
  const t = useT();
  const fields = Object.entries(block.schema?.properties ?? {});
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const submit = useMutation({
    mutationFn: async () => {
      const body = Object.fromEntries(
        fields.map(([name, spec]) => [
          name,
          spec.type === "number" || spec.type === "integer"
            ? Number(values[name] ?? 0)
            : (values[name] ?? ""),
        ]),
      );
      // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
      return (await api.POST(`/api/v1/plugins/${plugin}/${block.action}` as any, { body: body as any }))
        .data as DataState;
    },
  });
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit.mutate();
  };
  const title = block.title_key ? t(block.title_key) : "";
  return (
    <form className="ds-card ds-stack" aria-label={title} onSubmit={onSubmit}>
      <h2>{title}</h2>
      {fields.map(([name, spec]) =>
        spec.type === "boolean" ? (
          <CheckboxField
            key={name}
            label={name}
            checked={Boolean(values[name])}
            onChange={(e) => setValues({ ...values, [name]: e.target.checked })}
          />
        ) : (
          <TextField
            key={name}
            label={name}
            type={spec.type === "number" || spec.type === "integer" ? "number" : "text"}
            maxLength={spec.maxLength}
            required={(block.schema?.required ?? []).includes(name)}
            value={String(values[name] ?? "")}
            onChange={(e) => setValues({ ...values, [name]: e.target.value })}
          />
        ),
      )}
      {submit.isSuccess && submit.data?.message ? <p role="status">{submit.data.message}</p> : null}
      {submit.isError ? <FunctionalState state="error" /> : null}
      <Button type="submit" disabled={submit.isPending}>
        {t(block.submit_key ?? "plugins:page.submit")}
      </Button>
    </form>
  );
}

/**
 * ``/plugins/:pluginKey/:pageKey`` (spec 023 T032): a plugin page rendered from its declarative blocks with
 * design-system components only — sanitized Markdown (011), data blocks with functional states, forms from
 * a JSON Schema posting to the plugin's own action. No plugin JavaScript is ever executed.
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
      <h1>{t(page.data.title_key)}</h1>
      {page.data.blocks.map((block, index) => {
        const key = `${block.kind}-${index}`;
        if (block.kind === "markdown") return <SafeHtml key={key} html={block.html ?? ""} diagrams={false} />;
        if (block.kind === "form") return <FormBlock key={key} plugin={pluginKey} block={block} />;
        return <DataBlock key={key} plugin={pluginKey} block={block} />;
      })}
    </div>
  );
}
