import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Campaign, type CampaignAction, useCampaignAdmin, useCampaignsAdmin } from "../api";
import { Timeline } from "../history/Timeline";
import { SimulationPanel } from "./SimulationPanel";
import "../campaigns.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

const TEMPLATE = JSON.stringify(
  {
    names: { en: "Halloween", fr: "Halloween" },
    timezone: "Europe/Paris",
    schedule: {
      start_at: "2026-10-20T00:00:00",
      end_at: "2026-11-01T00:00:00",
      recurrence: { kind: "yearly" },
    },
    modifiers: [
      { id: "horror_xp", value: "xp", factor: 2, when: { media_kind: ["movie"], genre: ["horror"] } },
    ],
  },
  null,
  2,
);

function parse(text: string): Record<string, unknown> | null {
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Campaign console (spec 014, ``campaigns.manage``): every save publishes a new version; activation,
 * deactivation and cancellation need a reason and a confirmation; simulation and history per campaign.
 */
export default function CampaignConsole() {
  const t = useT();
  const campaigns = useCampaignsAdmin();
  const admin = useCampaignAdmin();
  const [key, setKey] = useState("");
  const [text, setText] = useState(TEMPLATE);
  const [invalid, setInvalid] = useState(false);
  const create = () => {
    const definition = parse(text);
    setInvalid(definition === null);
    if (definition && key) admin.create.mutate({ key, definition }, { onError: () => setInvalid(true) });
  };
  return (
    <div className="ds-stack campaign-console">
      <PageHeader icon="star" title={t("campaigns:admin.title")} />
      <section aria-labelledby="campaign-new" className="ds-stack">
        <h2 id="campaign-new">{t("campaigns:admin.create")}</h2>
        <TextField label={t("campaigns:admin.key")} value={key} onChange={(e) => setKey(e.target.value)} />
        <label htmlFor="campaign-definition">{t("campaigns:admin.definition")}</label>
        <textarea
          id="campaign-definition"
          rows={12}
          value={text}
          aria-invalid={invalid || undefined}
          onChange={(e) => setText(e.target.value)}
        />
        {invalid ? <p role="alert">{t("campaigns:admin.invalid")}</p> : null}
        <Button onClick={create} disabled={!key || admin.create.isPending}>
          {t("campaigns:admin.save")}
        </Button>
      </section>
      {(campaigns.data ?? []).map((campaign) => (
        <CampaignCard key={campaign.id} campaign={campaign} />
      ))}
    </div>
  );
}

function CampaignCard({ campaign }: { campaign: Campaign }) {
  const t = useT();
  const admin = useCampaignAdmin();
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<{ action: CampaignAction; token: string } | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const act = (action: CampaignAction, token?: string) =>
    admin.act.mutate(
      { id: campaign.id, action, reason, ...(token ? { confirmation: token } : {}) },
      {
        onSuccess: () => setPending(null),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "authz.confirmation_required") {
            setPending({ action, token: String(error.extensions.confirmation ?? "") });
          }
        },
      },
    );
  return (
    <section className="ds-card ds-stack" aria-labelledby={`campaign-${campaign.id}`}>
      <h2 id={`campaign-${campaign.id}`}>{campaign.key}</h2>
      <p>{t("campaigns:admin.state", { state: campaign.state, version: campaign.current_version })}</p>
      <TextField
        label={t("campaigns:admin.reason")}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="ds-stack--row">
        {(["activate", "deactivate", "cancel"] as const).map((action) => (
          <Button
            key={action}
            variant="secondary"
            disabled={reason.trim().length < 3}
            onClick={() => act(action)}
          >
            {t(`campaigns:admin.${action}`)}
          </Button>
        ))}
        <Button variant="secondary" onClick={() => admin.archive.mutate(campaign.id)}>
          {t("campaigns:admin.archive")}
        </Button>
        <Button variant="secondary" onClick={() => setShowHistory(!showHistory)} aria-expanded={showHistory}>
          {t("campaigns:admin.history")}
        </Button>
      </div>
      {pending ? (
        <div role="alertdialog" aria-labelledby={`campaign-confirm-${campaign.id}`} className="ds-card">
          <p id={`campaign-confirm-${campaign.id}`}>{t("campaigns:admin.confirm")}</p>
          <Button onClick={() => act(pending.action, pending.token)}>
            {t(`campaigns:admin.${pending.action}`)}
          </Button>
        </div>
      ) : null}
      <SimulationPanel campaignId={campaign.id} />
      {showHistory ? <Timeline campaignId={campaign.id} /> : null}
    </section>
  );
}
