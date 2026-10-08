import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { api } from "../../api/client";
import {
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminStats,
  FormActions,
  StatusBadge,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { MarkdownEditor } from "../content/MarkdownEditor";
import { SafeHtml } from "../content/SafeHtml";
import { MY_TERMS_KEY, useMyTerms, usePublishTerms, useTermsAdmin } from "./api";
import "../admin/admin.css";
import "./terms.css";

/**
 * Terms of use (027, Communication): optional — nothing is asked while nothing is published or while the
 * switch is off. A new version starts from the one in force; « members must accept again » (the default)
 * brings every member the acceptance sheet, a mere correction does not. The history counts acceptances.
 */
function Enforcement({ enabled }: { enabled: boolean }) {
  const t = useT();
  const client = useQueryClient();
  const change = useMutation({
    mutationFn: async (next: boolean) =>
      api.PUT("/api/v1/admin/terms/enforcement", { body: { enabled: next } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["admin", "terms"] });
      void client.invalidateQueries({ queryKey: ["terms"] });
      void client.invalidateQueries({ queryKey: MY_TERMS_KEY });
    },
  });
  return (
    <div className="terms-admin__switch">
      <p className="admin-muted">
        <Icon name="info" size={14} /> {t("admin:terms.optional")}
      </p>
      <CheckboxField
        label={t("admin:terms.enabled")}
        hint={t("admin:terms.enabledHint")}
        checked={enabled}
        disabled={change.isPending}
        onChange={(event) => change.mutate(event.target.checked)}
      />
    </div>
  );
}

function Editor({ base, next }: { base: { title: string; body_md: string } | undefined; next: number }) {
  const t = useT();
  const publish = usePublishTerms();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [body, setBody] = useState("");
  const [requires, setRequires] = useState(true);
  const [confirm, setConfirm] = useState(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: start from the version in force once it loads
  useEffect(() => {
    setTitle(base?.title ?? t("admin:terms.pageTitle"));
    setBody(base?.body_md ?? t("admin:terms.template"));
  }, [base?.title, base?.body_md]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setConfirm(true);
  };
  const send = () =>
    publish.mutate(
      { title, summary, body_md: body, requires_acceptance: next === 1 || requires },
      {
        onSuccess: () => {
          setSummary("");
          setConfirm(false);
        },
      },
    );
  return (
    <AdminSection
      title={t("admin:terms.editor")}
      description={t("admin:terms.editorHint")}
      icon="feather"
      span="full"
    >
      <form onSubmit={submit} className="admin-form terms-admin__form">
        <TextField
          label={t("admin:terms.titleField")}
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <div className="ds-field">
          <label htmlFor="terms-summary">{t("admin:terms.summary")}</label>
          <textarea
            id="terms-summary"
            rows={2}
            maxLength={1000}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          <span className="ds-field__hint">{t("admin:terms.summaryHint")}</span>
        </div>
        <MarkdownEditor label={t("admin:terms.body")} value={body} onChange={setBody} />
        {next > 1 ? (
          <CheckboxField
            label={t("admin:terms.requires")}
            hint={t("admin:terms.requiresHint")}
            checked={requires}
            onChange={(e) => setRequires(e.target.checked)}
          />
        ) : null}
        {publish.isSuccess ? (
          <p role="status" className="services-admin__ok">
            {t("admin:terms.published", { version: publish.data.version })}
          </p>
        ) : null}
        {publish.isError ? (
          <p role="alert" className="services-admin__ko">
            {publish.error instanceof ApiError ? publish.error.message : t("admin:terms.failed")}
          </p>
        ) : null}
        <FormActions>
          <Dialog
            open={confirm}
            onOpenChange={setConfirm}
            title={t("admin:terms.publish")}
            description={t("admin:terms.confirm", { version: next })}
            trigger={
              <Button type="submit" disabled={!title.trim() || !body.trim() || publish.isPending}>
                <Icon name="shield" size={16} />
                {t("admin:terms.publish")}
              </Button>
            }
            footer={
              <Button onClick={send} disabled={publish.isPending}>
                {t("admin:terms.publish")}
              </Button>
            }
          >
            <span />
          </Dialog>
        </FormActions>
      </form>
    </AdminSection>
  );
}

export default function TermsAdmin() {
  const t = useT();
  const format = useFormat();
  const admin = useTermsAdmin();
  useMyTerms(); // the publisher's own standing refreshes with the publication
  const versions = admin.data?.versions ?? [];
  const current = versions[0];
  const enabled = admin.data?.enabled ?? true;
  const [reading, setReading] = useState<number | null>(null);
  return (
    <AdminPage icon="shield" title={t("admin:terms.pageTitle")} description={t("admin:terms.subtitle")}>
      <AdminStats
        label={t("admin:terms.pageTitle")}
        stats={[
          {
            key: "state",
            label: t("admin:terms.state"),
            value: enabled && current ? t("admin:terms.on") : t("admin:terms.off"),
            icon: "shield",
            tone: enabled && current ? "ok" : "neutral",
          },
          {
            key: "current",
            label: t("admin:terms.current"),
            value: current ? `v${current.version}` : t("admin:terms.none"),
            hint: current ? format.date(current.published_at) : undefined,
            icon: "scroll",
            tone: "info",
          },
          {
            key: "up",
            label: t("admin:terms.upToDate"),
            value: format.number(admin.data?.members_up_to_date ?? 0),
            icon: "users",
            tone: "ok",
          },
          {
            key: "versions",
            label: t("admin:terms.versions"),
            value: format.number(versions.length),
            icon: "hourglass",
            tone: "neutral",
          },
        ]}
      />
      <AdminGrid>
        <AdminSection title={t("admin:terms.state")} icon="shield" span="full">
          <Enforcement enabled={enabled} />
        </AdminSection>
        <Editor base={current} next={(current?.version ?? 0) + 1} />
        <AdminSection title={t("admin:terms.history")} icon="hourglass" span="full" flush>
          {admin.data && !versions.length ? (
            <p className="admin-muted admin-pad">{t("admin:terms.noHistory")}</p>
          ) : null}
          <ul className="admin-list">
            {versions.map((version) => (
              <li key={version.version}>
                <span className="admin-list__main">
                  <strong>
                    v{version.version} · {version.title}
                  </strong>
                  <span className="admin-muted">
                    {format.dateTime(version.published_at)} ·{" "}
                    {t("admin:terms.acceptances", { count: version.acceptances })}
                    {version.summary ? ` · ${version.summary}` : ""}
                  </span>
                </span>
                <StatusBadge tone={version.requires_acceptance ? "info" : "neutral"}>
                  {version.requires_acceptance ? t("admin:terms.toAccept") : t("admin:terms.correction")}
                </StatusBadge>
                <Dialog
                  size="lg"
                  open={reading === version.version}
                  onOpenChange={(open) => setReading(open ? version.version : null)}
                  title={`v${version.version} · ${version.title}`}
                  closeLabel={t("shell:terms.close")}
                  trigger={<Button variant="secondary">{t("admin:terms.view")}</Button>}
                >
                  <SafeHtml html={version.html} diagrams={false} />
                </Dialog>
              </li>
            ))}
          </ul>
        </AdminSection>
      </AdminGrid>
    </AdminPage>
  );
}
