import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type AdminAction, type Project, useProjectAdmin, useProjects } from "../api";

interface Move {
  action: AdminAction;
  label: string;
  body: Record<string, unknown>;
}

function moves(project: Project): Move[] {
  switch (project.state) {
    case "idea":
      return [{ action: "promote", label: "promote", body: {} }];
    case "proposal":
      return [{ action: "open", label: "open", body: { rules: {} } }];
    case "open":
      return [{ action: "transition", label: "toValidation", body: { to: "validation" } }];
    case "validation":
      return [
        { action: "validate", label: "approve", body: { approve: true } },
        { action: "validate", label: "decline", body: { approve: false } },
      ];
    case "development":
      return [
        { action: "transition", label: "toBeta", body: { to: "beta" } },
        { action: "transition", label: "release", body: { to: "released" } },
      ];
    case "beta":
      return [{ action: "transition", label: "release", body: { to: "released" } }];
    default:
      return [];
  }
}

/**
 * Project console (spec 015 T014, ``projects.manage``): move projects through the lifecycle. Decisions
 * that move members' Coins ask for a confirmation, then are retried with it.
 */
export default function ProjectConsole() {
  const t = useT();
  const projects = useProjects();
  const admin = useProjectAdmin();
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<{ project: Project; move: Move; confirmation: string } | null>(null);

  const run = (project: Project, move: Move, confirmation?: string) => {
    const body = { ...move.body, reason: reason || undefined, version: project.version, confirmation };
    admin.mutate(
      { projectId: project.id, action: move.action, body },
      {
        onSuccess: () => setPending(null),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "authz.confirmation_required") {
            setPending({ project, move, confirmation: String(error.extensions.confirmation ?? "") });
          }
        },
      },
    );
  };

  return (
    <div className="ds-stack">
      <PageHeader icon="shop" title={t("marketplace:console.title")} />
      <TextField
        label={t("marketplace:console.reason")}
        value={reason}
        maxLength={500}
        onChange={(e) => setReason(e.target.value)}
      />
      {pending ? (
        <div role="alertdialog" aria-labelledby="project-confirm" className="ds-card ds-stack">
          <p id="project-confirm">{t("marketplace:console.confirm", { project: pending.project.title })}</p>
          <div className="ds-stack--row">
            <Button onClick={() => run(pending.project, pending.move, pending.confirmation)}>
              {t("marketplace:console.confirmYes")}
            </Button>
            <Button variant="secondary" onClick={() => setPending(null)}>
              {t("marketplace:console.confirmNo")}
            </Button>
          </div>
        </div>
      ) : null}
      {projects.isError ? <FunctionalState state="unavailable" /> : null}
      <ul className="ds-stack">
        {(projects.data ?? []).map((project) => (
          <li key={project.id} className="ds-card ds-stack">
            <h2>{project.title}</h2>
            <p className="ds-badge">{t(`marketplace:state.${project.state}`)}</p>
            <div className="ds-stack--row">
              {moves(project).map((move) => (
                <Button key={move.label} variant="secondary" onClick={() => run(project, move)}>
                  {t(`marketplace:console.${move.label}`)}
                </Button>
              ))}
              {["rejected", "abandoned", "released"].includes(project.state) ? null : (
                <>
                  {["idea", "proposal", "open", "validation"].includes(project.state) ? (
                    <Button
                      variant="secondary"
                      onClick={() => run(project, { action: "reject", label: "reject", body: {} })}
                    >
                      {t("marketplace:console.reject")}
                    </Button>
                  ) : null}
                  <Button
                    variant="secondary"
                    onClick={() => run(project, { action: "abandon", label: "abandon", body: {} })}
                  >
                    {t("marketplace:console.abandon")}
                  </Button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
