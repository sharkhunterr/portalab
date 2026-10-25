import { type ReactNode, useState } from "react";
import { AdminEmpty, AdminPage, AdminSection, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import {
  type Campaign,
  type CampaignAction,
  discountScope,
  useCampaignAdmin,
  useCampaignsAdmin,
} from "../api";
import { Timeline } from "../history/Timeline";
import { type CampaignDef, CampaignEditor, gainsOf } from "./CampaignEditor";
import { SimulationPanel } from "./SimulationPanel";
import "../campaigns.css";
import "../../gamification/gamification.css";

const TONES: Record<string, "ok" | "bad" | "info" | "neutral"> = {
  active: "ok",
  cancelled: "bad",
  scheduled: "info",
};

/**
 * Campaign console (spec 014; 027 redesign, ``campaigns.manage``): one card per campaign — when it runs,
 * its bonuses and shop discounts in words — edited in a form (each save publishes a new version);
 * activation, deactivation and cancellation need a reason and a confirmation; simulation and history.
 */
/** The way to create a campaign (issue 253: also in the arrival wizard). */
export function CreateCampaign() {
  const t = useT();
  const [creating, setCreating] = useState(false);
  return (
    <Dialog
      open={creating}
      onOpenChange={setCreating}
      title={t("campaigns:admin.create")}
      closeLabel={t("campaigns:editor.close")}
      size="lg"
      trigger={
        <Button>
          <Icon name="plus" size={16} />
          {t("campaigns:admin.create")}
        </Button>
      }
    >
      <CampaignEditor onDone={() => setCreating(false)} />
    </Dialog>
  );
}

/** The campaigns, each a card (issue 253: also in the arrival wizard). */
export function CampaignList() {
  const t = useT();
  const campaigns = useCampaignsAdmin();
  return (
    <>
      {campaigns.data && !campaigns.data.length ? (
        <AdminEmpty icon="star" title={t("campaigns:editor.empty")} />
      ) : null}
      <div className="campaign-cards">
        {(campaigns.data ?? []).map((campaign) => (
          <CampaignCard key={campaign.id} campaign={campaign} />
        ))}
      </div>
    </>
  );
}

export default function CampaignConsole() {
  const t = useT();
  return (
    <AdminPage
      icon="star"
      title={t("campaigns:admin.title")}
      description={t("campaigns:admin.description")}
      primary={<CreateCampaign />}
    >
      <CampaignList />
    </AdminPage>
  );
}

/** A disclosure whose content is only built (and fetched) once opened. */
function Lazy({ summary, children }: { summary: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="gam-advanced" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{summary}</summary>
      {open ? children : null}
    </details>
  );
}

function CampaignCard({ campaign }: { campaign: Campaign }) {
  const t = useT();
  const format = useFormat();
  const admin = useCampaignAdmin();
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<{ action: CampaignAction; token: string } | null>(null);
  const def = campaign.definition as unknown as CampaignDef;
  const name = def.names?.fr || def.names?.en || campaign.key;
  const when = (value?: string | null) => (value ? format.dateTime(`${value.slice(0, 19)}`) : "—");
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
    <AdminSection
      title={name}
      icon="star"
      description={def.description || undefined}
      actions={
        <>
          <StatusBadge tone={TONES[campaign.state] ?? "neutral"}>
            {t("campaigns:admin.state", { state: campaign.state, version: campaign.current_version })}
          </StatusBadge>
          <Dialog
            open={editing}
            onOpenChange={setEditing}
            title={name}
            closeLabel={t("campaigns:editor.close")}
            size="lg"
            trigger={
              <Button variant="secondary">
                <Icon name="settings" size={16} />
                {t("campaigns:editor.edit")}
              </Button>
            }
          >
            <CampaignEditor campaign={campaign} onDone={() => setEditing(false)} />
          </Dialog>
        </>
      }
    >
      <p className="campaign-when">
        <Icon name="calendar" size={14} /> {when(def.schedule?.start_at)} → {when(def.schedule?.end_at)}
        {def.schedule?.recurrence?.kind === "yearly" ? ` · ${t("campaigns:editor.yearly")}` : ""}
      </p>
      <div className="gam-chips">
        {(def.modifiers ?? []).map((bonus) => (
          <span key={bonus.id} className="gam-chip" data-value={gainsOf(bonus)[0]?.value}>
            {gainsOf(bonus)
              .map((g) => `×${g.factor} ${t(`gamification:value.${g.value}`)}`)
              .join(" + ")}
            {bonus.when.media_kind?.length
              ? ` · ${bonus.when.media_kind.map((k) => t(`media:kind.${k}`)).join(", ")}`
              : ""}
            {bonus.when.genre?.length ? ` · ${bonus.when.genre.join(", ")}` : ""}
          </span>
        ))}
        {(def.discounts ?? []).map((discount) => (
          <span key={discount.id} className="gam-chip" data-kind="shop">
            <Icon name="shop" size={12} /> −{discount.percent} % ·{" "}
            {discountScope(t, {
              everything: discount.everything,
              seasons: discount.seasons,
              categories: discount.categories,
              products: discount.products.length,
            })}
          </span>
        ))}
      </div>
      <details className="gam-advanced">
        <summary>{t("campaigns:editor.control")}</summary>
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
          <Button variant="ghost" onClick={() => admin.archive.mutate(campaign.id)}>
            {t("campaigns:admin.archive")}
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
      </details>
      <Lazy summary={t("campaigns:admin.simulate")}>
        <SimulationPanel campaignId={campaign.id} />
      </Lazy>
      <Lazy summary={t("campaigns:admin.history")}>
        <Timeline campaignId={campaign.id} />
      </Lazy>
    </AdminSection>
  );
}
