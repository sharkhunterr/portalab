import { useState } from "react";
import { AdminSection, KeyValues } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { packPath, useVisualAction, type VersionDetail } from "../api";
import { nameOf, OutcomeBadge } from "../parts";
import { missingConfirmations } from "./review";

/** Validation: what is decided, then published (its elements in the shop with the decided economy, the
 * version live) — or refused with a reason. A version with a blocking finding, or missing a confirmation,
 * cannot be published. */
export function ValidationStep({ detail }: { detail: VersionDetail }) {
  const t = useT();
  const action = useVisualAction();
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const given = detail.draft?.confirmations ?? {};
  const missing = missingConfirmations(detail, given);
  const blocked = !detail.report.summary.publishable;
  const changed = Object.keys(detail.draft?.economy ?? {}).length;
  const name = nameOf(detail.names, detail.pack);
  const call = async (path: string, body: unknown) => {
    setError(null);
    try {
      await action.mutateAsync({ path, body });
      return true;
    } catch (failure) {
      setError(String((failure as Error).message));
      return false;
    }
  };

  if (detail.step === "published" || detail.step === "superseded") {
    return (
      <AdminSection
        title={t("admin:visuals.step.validation")}
        icon="check"
        actions={<OutcomeBadge outcome="done" />}
      >
        <p>
          {detail.current
            ? t("admin:visuals.validation.live")
            : t("admin:visuals.validation.former", { at: detail.published_at ?? "" })}
        </p>
      </AdminSection>
    );
  }
  if (detail.step === "refused" || detail.step === "purged") {
    return (
      <AdminSection
        title={t("admin:visuals.step.validation")}
        icon="close"
        actions={<OutcomeBadge outcome="blocking" />}
      >
        <p>{t("admin:visuals.validation.refused", { reason: detail.decision?.reason || "—" })}</p>
      </AdminSection>
    );
  }
  return (
    <AdminSection title={t("admin:visuals.step.validation")} icon="check">
      <KeyValues
        items={[
          {
            key: "elements",
            label: t("admin:visuals.field.elements"),
            value: t("admin:visuals.elements", { count: detail.report.elements.length }),
          },
          {
            key: "economy",
            label: t("admin:visuals.review.economy"),
            value: t("admin:visuals.validation.changed", { count: changed }),
          },
          {
            key: "tested",
            label: t("admin:visuals.step.test"),
            value: detail.tested ? t("admin:visuals.outcome.done") : t("admin:visuals.validation.untested"),
          },
        ]}
      />
      {blocked ? <FunctionalState state="error" label={t("admin:visuals.blocked")} /> : null}
      {!blocked && missing.length ? (
        <FunctionalState
          state="partial"
          label={t("admin:visuals.validation.missing", { items: missing.join(", ") })}
        />
      ) : null}
      {error ? <FunctionalState state="error" label={error} /> : null}
      <div className="ds-stack--row">
        <Dialog
          open={confirming}
          onOpenChange={setConfirming}
          title={t("admin:visuals.validation.publishTitle", { pack: name, version: detail.version })}
          description={t("admin:visuals.validation.publishHelp")}
          closeLabel={t("admin:visuals.cancel")}
          trigger={
            <Button disabled={blocked || missing.length > 0 || action.isPending}>
              <Icon name="check" size={16} /> {t("admin:visuals.approve")}
            </Button>
          }
        >
          <DialogActions>
            <Button
              onClick={async () => {
                const ok = await call(`${packPath(detail.pack, detail.version)}/publish`, {
                  economy: detail.draft?.economy ?? {},
                  confirmations: { scripts: false, replaces: [], contracts: [], ...given },
                });
                if (ok) setConfirming(false);
              }}
            >
              {t("admin:visuals.approve")}
            </Button>
          </DialogActions>
        </Dialog>
      </div>
      <div className="visuals-refuse">
        <TextField
          label={t("admin:visuals.validation.reason")}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        <Button
          variant="secondary"
          disabled={action.isPending}
          onClick={() => void call(`${packPath(detail.pack, detail.version)}/refuse`, { reason })}
        >
          {t("admin:visuals.reject")}
        </Button>
      </div>
    </AdminSection>
  );
}
