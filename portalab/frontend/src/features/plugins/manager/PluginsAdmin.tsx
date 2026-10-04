import { useState } from "react";
import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Badge } from "../../../design-system/components/Content";
import { TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Review, useDiscovery, usePluginActions, usePluginDetail, usePlugins } from "../api";
import { Diagnostics } from "../diagnostics/Diagnostics";
import { ReviewConsent } from "../review/ReviewConsent";

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
        {!plugin.approved ? (
          <Button onClick={() => run("approve")}>{t("plugins:actions.approve")}</Button>
        ) : null}
        {["installed", "disabled", "incompatible", "quarantined"].includes(plugin.state) ? (
          <Button onClick={() => run("enable")}>{t("plugins:actions.enable")}</Button>
        ) : null}
        {plugin.state === "enabled" ? (
          <Button
            variant="secondary"
            onClick={() =>
              run(
                "disable",
                { cascade: data.dependents.length > 0 },
                t("plugins:confirm.cascade", { list: data.dependents.join(", ") }),
              )
            }
          >
            {t("plugins:actions.disable")}
          </Button>
        ) : null}
        {["installed", "disabled", "incompatible", "quarantined"].includes(plugin.state) ? (
          <Button variant="secondary" onClick={() => run("archive")}>
            {t("plugins:actions.archive")}
          </Button>
        ) : null}
        {plugin.state !== "enabled" ? (
          <Button
            variant="secondary"
            onClick={() => run("purge", { export: true }, t("plugins:confirm.purge"))}
          >
            {t("plugins:actions.purge")}
          </Button>
        ) : null}
      </div>
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
  const discovery = useDiscovery();
  const action = usePluginActions();
  const [open, setOpen] = useState<string | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const restart = (plugins.data ?? []).some((p) => p.needs_restart);
  const install = (pkg: string) =>
    action.mutate(
      { path: "/api/v1/admin/plugins/install", body: { package: pkg } },
      { onSuccess: (data) => setReview((data as { review: Review }).review) },
    );
  return (
    <AdminPage icon="plug" title={t("plugins:title")} description={t("plugins:description")}>
      {restart ? <FunctionalState state="maintenance" label={t("plugins:restartBanner")} /> : null}
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
      <AdminSection title={t("plugins:installed")} icon="plug">
        {plugins.isError ? <FunctionalState state="unavailable" /> : null}
        {plugins.data?.length === 0 ? <p>{t("plugins:none")}</p> : null}
        <ul className="ds-stack">
          {(plugins.data ?? []).map((plugin) => (
            <li key={plugin.key} className="ds-card ds-stack">
              <div className="ds-stack--row">
                <strong>{plugin.name}</strong> <span>{plugin.version}</span>
                <Badge
                  tone={
                    plugin.state === "enabled"
                      ? "available"
                      : plugin.state === "quarantined"
                        ? "error"
                        : "neutral"
                  }
                >
                  {t(`plugins:state.${plugin.state}`)}
                </Badge>
                <Badge>{t(`plugins:maturity.${plugin.maturity}`)}</Badge>
                {plugin.needs_restart ? <Badge tone="maintenance">{t("plugins:needsRestart")}</Badge> : null}
                <Button
                  variant="secondary"
                  aria-expanded={open === plugin.key}
                  onClick={() => setOpen(open === plugin.key ? null : plugin.key)}
                >
                  {t("plugins:details")}
                </Button>
              </div>
              {plugin.quarantine_reason ? <p>{plugin.quarantine_reason}</p> : null}
              {open === plugin.key ? <PluginDetail pluginKey={plugin.key} /> : null}
            </li>
          ))}
        </ul>
      </AdminSection>
      <AdminSection title={t("plugins:discovery")} description={t("plugins:discoveryHint")} icon="compass">
        <ul className="ds-stack">
          {(discovery.data ?? []).map((item) => (
            <li key={item.package} className="ds-card ds-stack--row">
              <span>
                {item.name ?? item.package} {item.version ?? ""}{" "}
                {item.maturity ? <Badge>{t(`plugins:maturity.${item.maturity}`)}</Badge> : null}
              </span>
              {!item.valid ? <FunctionalState state="error" label={t("plugins:invalidPackage")} /> : null}
              {item.compatibility?.length ? (
                <FunctionalState state="error" label={item.compatibility.join("; ")} />
              ) : null}
              {item.deprecation_notice ? <span>{item.deprecation_notice}</span> : null}
              {item.valid && !item.state ? (
                <Button onClick={() => install(item.package)}>{t("plugins:actions.install")}</Button>
              ) : null}
            </li>
          ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}
