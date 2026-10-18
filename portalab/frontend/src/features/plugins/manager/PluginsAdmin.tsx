import { useState } from "react";
import {
  AdminPage,
  AdminSection,
  SearchBox,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Badge } from "../../../design-system/components/Content";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Menu } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { ImportPanel } from "../../extensions/ImportPanel";
import "../../visuals/visuals.css";
import {
  type PluginRow,
  type Review,
  useDiscovery,
  usePluginActions,
  usePluginDetail,
  usePlugins,
  useUploadPlugin,
} from "../api";
import { Diagnostics } from "../diagnostics/Diagnostics";
import { ReviewConsent } from "../review/ReviewConsent";
import { Confinement } from "./Confinement";

function PluginDetail({ pluginKey }: { pluginKey: string }) {
  const t = useT();
  const detail = usePluginDetail(pluginKey);
  const action = usePluginActions();
  const [updatePackage, setUpdatePackage] = useState("");
  const data = detail.data?.detail;
  if (!data) return null;
  const plugin = data.plugin;
  const run = (suffix: string, body: Record<string, unknown> = {}, question?: string) =>
    action.mutate({
      path: `/api/v1/admin/plugins/${pluginKey}/${suffix}`,
      body,
      confirm: () => window.confirm(question ?? t("plugins:confirm.generic")),
    });
  return (
    <div className="ds-stack">
      {data.deprecation_notice ? <FunctionalState state="stale" label={data.deprecation_notice} /> : null}
      {data.dependencies.length ? (
        <FunctionalState
          state="error"
          label={t("plugins:detail.dependencies", { list: data.dependencies.join("; ") })}
        />
      ) : null}
      {data.dependents.length ? (
        <p>{t("plugins:detail.dependents", { list: data.dependents.join(", ") })}</p>
      ) : null}
      <div className="ds-stack--row">
        <TextField
          label={t("plugins:update.package")}
          value={updatePackage}
          onChange={(e) => setUpdatePackage(e.target.value)}
        />
        <Button
          variant="secondary"
          disabled={!updatePackage}
          onClick={() => run("update", { package: updatePackage })}
        >
          {t("plugins:actions.update")}
        </Button>
        {plugin.state === "update_pending" ? (
          <Button onClick={() => run("update/confirm-restart")}>{t("plugins:actions.confirmRestart")}</Button>
        ) : null}
        <Button variant="secondary" onClick={() => run("rollback")}>
          {t("plugins:actions.rollback")}
        </Button>
      </div>
      {action.error instanceof ApiError ? <p role="alert">{action.error.message}</p> : null}
      <Confinement pluginKey={pluginKey} />
      <Diagnostics pluginKey={pluginKey} />
    </div>
  );
}

/**
 * ``/admin/plugins`` (spec 023 T033): installed plugins with state and maturity (text, not color), the
 * restart banner, discovery of available packages with a compatibility preview, install with review and
 * consent, and per-plugin lifecycle, updates, purge and diagnostics.
 */
export default function PluginsAdmin() {
  const t = useT();
  const plugins = usePlugins();
  const action = usePluginActions();
  const [open, setOpen] = useState<string | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const restart = (plugins.data ?? []).some((p) => p.needs_restart);
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const list = (plugins.data ?? []).filter(
    (p) => !q || p.key.includes(q) || p.name.toLowerCase().includes(q),
  );
  const install = (pkg: string) =>
    action.mutate(
      { path: "/api/v1/admin/plugins/install", body: { package: pkg } },
      { onSuccess: (data) => setReview((data as { review: Review }).review) },
    );
  return (
    <AdminPage icon="plug" title={t("plugins:title")} description={t("plugins:description")} wide>
      {restart ? <FunctionalState state="maintenance" label={t("plugins:restartBanner")} /> : null}
      <PluginImport onReview={setReview} onInstall={install} />
      {review ? (
        <ReviewConsent
          review={review}
          onApprove={() => {
            action.mutate({ path: `/api/v1/admin/plugins/${review.key}/approve` });
            setReview(null);
          }}
          onCancel={() => setReview(null)}
        />
      ) : null}
      <AdminSection title={t("plugins:installed")} icon="plug" flush>
        <div className="vp-toolbar">
          <SearchBox label={t("plugins:search")} value={query} onChange={setQuery} />
        </div>
        {plugins.isError ? <FunctionalState state="unavailable" /> : null}
        {plugins.data?.length === 0 ? <p className="visuals-empty">{t("plugins:none")}</p> : null}
        <ul className="vp-list vp-list__packs">
          {list.map((plugin) => (
            <PluginCard
              key={plugin.key}
              plugin={plugin}
              open={open === plugin.key}
              onToggle={() => setOpen(open === plugin.key ? null : plugin.key)}
            />
          ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}

const STATE_TONE: Record<string, Tone> = {
  enabled: "ok",
  disabled: "neutral",
  installed: "info",
  archived: "neutral",
  needs_configuration: "warn",
  update_pending: "info",
  update_failed: "bad",
  incompatible: "bad",
  quarantined: "bad",
};
const STOPPED = ["installed", "disabled", "incompatible", "quarantined"];

/**
 * Issue 152: one installed plugin as Extensions shows every extension (its visual packs, its widgets) — its
 * name, key, how its code runs and where it came from, its state and version, its actions in a menu, its
 * settings, confinement and diagnostics folded below.
 */
function PluginCard({ plugin, open, onToggle }: { plugin: PluginRow; open: boolean; onToggle: () => void }) {
  const t = useT();
  const action = usePluginActions();
  const detail = usePluginDetail(plugin.key);
  const dependents = detail.data?.detail?.dependents ?? [];
  const run = (suffix: string, body: Record<string, unknown> = {}, question?: string) =>
    action.mutate({
      path: `/api/v1/admin/plugins/${plugin.key}/${suffix}`,
      body,
      confirm: () => window.confirm(question ?? t("plugins:confirm.generic")),
    });
  const items = [
    ...(!plugin.approved
      ? [
          {
            key: "approve",
            icon: "check",
            label: t("plugins:actions.approve"),
            onSelect: () => run("approve"),
          },
        ]
      : []),
    ...(STOPPED.includes(plugin.state)
      ? [{ key: "enable", icon: "play", label: t("plugins:actions.enable"), onSelect: () => run("enable") }]
      : []),
    ...(plugin.state === "enabled"
      ? [
          {
            key: "disable",
            icon: "pause",
            label: t("plugins:actions.disable"),
            onSelect: () =>
              run(
                "disable",
                { cascade: dependents.length > 0 },
                t("plugins:confirm.cascade", { list: dependents.join(", ") }),
              ),
          },
        ]
      : []),
    ...(plugin.state === "update_pending"
      ? [
          {
            key: "restart",
            icon: "play",
            label: t("plugins:actions.confirmRestart"),
            onSelect: () => run("update/confirm-restart"),
          },
        ]
      : []),
    {
      key: "rollback",
      icon: "undo",
      label: t("plugins:actions.rollback"),
      onSelect: () => run("rollback"),
    },
    ...(STOPPED.includes(plugin.state)
      ? [
          {
            key: "archive",
            icon: "package",
            label: t("plugins:actions.archive"),
            onSelect: () => run("archive"),
          },
        ]
      : []),
    ...(plugin.state !== "enabled"
      ? [
          {
            key: "purge",
            icon: "trash",
            label: t("plugins:actions.purge"),
            separated: true,
            onSelect: () => run("purge", { export: true }, t("plugins:confirm.purge")),
          },
        ]
      : []),
  ];
  return (
    <li className="vp-card" data-state={plugin.state}>
      <div className="vp-card__head">
        <div className="vp-card__title">
          <button
            type="button"
            className="vp-card__name vp-card__toggle"
            aria-expanded={open}
            onClick={onToggle}
          >
            {plugin.name}
          </button>
          <span className="vp-card__meta">
            <code>{plugin.key}</code>
            {plugin.runtime ? ` · ${t(`plugins:runtime.${plugin.runtime}`)}` : ""}
            {` · ${t(`plugins:source.${plugin.source}`)}`}
          </span>
        </div>
        <div className="vp-card__state">
          <StatusBadge tone={STATE_TONE[plugin.state] ?? "neutral"}>
            {t("plugins:stateVersion", {
              state: t(`plugins:state.${plugin.state}`),
              version: plugin.version,
            })}
          </StatusBadge>
          <Menu
            label={t("plugins:menu", { name: plugin.name })}
            align="end"
            trigger={
              <Button
                variant="ghost"
                size="icon"
                disabled={action.isPending}
                aria-label={t("plugins:menu", { name: plugin.name })}
              >
                <Icon name="more" size={18} />
              </Button>
            }
            items={items}
          />
        </div>
      </div>
      <div className="vp-card__facts">
        <span className="visuals-flag">{t(`plugins:maturity.${plugin.maturity}`)}</span>
        {!plugin.approved ? <StatusBadge tone="warn">{t("plugins:toApprove")}</StatusBadge> : null}
        {plugin.needs_restart ? <StatusBadge tone="info">{t("plugins:needsRestart")}</StatusBadge> : null}
      </div>
      {plugin.quarantine_reason ? <p className="vp-message">{plugin.quarantine_reason}</p> : null}
      {action.error instanceof ApiError ? (
        <p className="vp-message" role="alert">
          {action.error.message}
        </p>
      ) : null}
      <button type="button" className="vp-waiting" aria-expanded={open} onClick={onToggle}>
        <Icon name="settings" size={16} />
        <span>{t(open ? "plugins:hideDetails" : "plugins:showDetails")}</span>
        <Icon name={open ? "chevron-down" : "chevron-right"} size={16} />
      </button>
      {open ? <PluginDetail pluginKey={plugin.key} /> : null}
    </li>
  );
}

/**
 * 028 (issue 138): Extensions → Plugins opens with its « Import »: the ``plugins/available`` folder read again
 * (what is found there, each with its compatibility, installed on demand) or a .zip sent; an install comes
 * back with its review to consent to. Nothing is ever downloaded on its own.
 */
function PluginImport({
  onReview,
  onInstall,
}: {
  onReview: (review: Review) => void;
  onInstall: (pkg: string) => void;
}) {
  const t = useT();
  const discovery = useDiscovery();
  const upload = useUploadPlugin();
  const [read, setRead] = useState(false);
  const found = (discovery.data ?? []).filter((item) => !item.state);
  return (
    <ImportPanel
      title={t("admin:extensions.import")}
      description={t("plugins:discoveryHint")}
      sources={[
        {
          key: "folder",
          icon: "folder",
          label: t("plugins:import.folder"),
          hint: "plugins/available",
          render: ({ className, children }) => (
            <button
              type="button"
              className={className}
              disabled={discovery.isFetching}
              onClick={async () => {
                await discovery.refetch();
                setRead(true);
              }}
            >
              {children}
            </button>
          ),
        },
        {
          key: "zip",
          icon: "inbox",
          label: t("plugins:import.zip"),
          hint: t("plugins:import.zipHint"),
          render: ({ className, children }) => (
            <label className={className}>
              <input
                className="ext-import__file"
                type="file"
                accept=".zip,application/zip"
                onChange={(event) => {
                  const chosen = event.target.files?.[0];
                  event.target.value = "";
                  if (chosen) upload.mutate(chosen, { onSuccess: (data) => onReview(data.review) });
                }}
              />
              {children}
            </label>
          ),
        },
      ]}
    >
      {upload.isError ? <FunctionalState state="error" label={upload.error.message} /> : null}
      {read && !found.length ? (
        <p className="ext-import__result" role="status">
          {t("plugins:import.nothing")}
        </p>
      ) : null}
      {found.length ? (
        <ul className="ext-import__found">
          {found.map((item) => (
            <li key={item.package}>
              <span>
                <strong>{item.name ?? item.package}</strong> {item.version ?? ""}{" "}
                {item.maturity ? <Badge>{t(`plugins:maturity.${item.maturity}`)}</Badge> : null}
              </span>
              {!item.valid ? <FunctionalState state="error" label={t("plugins:invalidPackage")} /> : null}
              {item.compatibility?.length ? (
                <FunctionalState state="error" label={item.compatibility.join("; ")} />
              ) : null}
              {item.valid && !item.compatibility?.length ? (
                <Button onClick={() => onInstall(item.package)}>{t("plugins:actions.install")}</Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </ImportPanel>
  );
}
