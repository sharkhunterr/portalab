import { useState } from "react";
import { Link } from "react-router";
import { AdminEmpty, AdminPage } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type AdminAction, type Project, useProjectAdmin, useProjects } from "../api";
import { Gathered, STATE_ICON, Stepper } from "../projects/parts";
import "../marketplace.css";

interface Move {
  action: AdminAction;
  label: string;
  body: Record<string, unknown>;
  tone?: "primary" | "danger";
}

/** What may happen to a project now — the way forward first, refusing or abandoning it last. */
function moves(project: Project): Move[] {
  const forward: Move[] = (() => {
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
  })();
  const ending: Move[] = [];
  if (["idea", "proposal", "open", "validation"].includes(project.state))
    ending.push({ action: "reject", label: "reject", body: {}, tone: "danger" });
  if (!["rejected", "abandoned", "released"].includes(project.state))
    ending.push({ action: "abandon", label: "abandon", body: {}, tone: "danger" });
  return [...forward.map((move, i) => (i === 0 ? { ...move, tone: "primary" as const } : move)), ...ending];
}

/** issue 303: the tabs — what waits for my decision, what runs, what is over. */
const TABS: Record<string, readonly string[]> = {
  decide: ["idea", "proposal", "validation"],
  running: ["open", "development", "beta"],
  done: ["released", "rejected", "abandoned"],
};

/** A decision on a project, in its own window: what it does, a public reason, and — when members' Coins
 * move — the confirmation the server asks for. */
function MoveButton({ project, move }: { project: Project; move: Move }) {
  const t = useT();
  const format = useFormat();
  const admin = useProjectAdmin();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  // issue 304: opening the funding sets its goal and each member's cap — frozen from then on
  const proposed = project.rules_frozen_at ? null : (project.totals.goal_amount ?? null);
  const [goal, setGoal] = useState(proposed ? String(proposed) : "");
  const [cap, setCap] = useState("1000");
  const opening = move.action === "open";
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const label = t(`marketplace:console.${move.label}`);
  const run = () =>
    admin.mutate(
      {
        projectId: project.id,
        action: move.action,
        body: {
          ...move.body,
          ...(opening
            ? {
                rules: {
                  max_funding_per_user: Number(cap) || 1000,
                  ...(Number(goal) > 0 ? { goal_amount: Number(goal) } : {}),
                },
              }
            : {}),
          reason: reason.trim() || undefined,
          version: project.version,
          confirmation: confirmation ?? undefined,
        },
      },
      {
        onSuccess: () => {
          setOpen(false);
          setConfirmation(null);
          setReason("");
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "authz.confirmation_required")
            setConfirmation(String(error.extensions.confirmation ?? ""));
        },
      },
    );
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setConfirmation(null);
      }}
      trigger={
        <Button
          variant={move.tone === "primary" ? "primary" : move.tone === "danger" ? "ghost" : "secondary"}
          data-tone={move.tone}
        >
          {label}
        </Button>
      }
      title={t("marketplace:console.moveTitle", { action: label, project: project.title })}
      description={t("marketplace:console.moveHint")}
      closeLabel={t("marketplace:console.confirmNo")}
      footer={
        <Button
          variant={move.tone === "danger" ? "danger" : "primary"}
          disabled={admin.isPending}
          onClick={run}
        >
          {confirmation ? t("marketplace:console.confirmYes") : label}
        </Button>
      }
    >
      {opening ? (
        <div className="project-admin__rules">
          <TextField
            type="number"
            min={1}
            label={t("marketplace:console.goal")}
            hint={
              proposed
                ? t("marketplace:console.goalProposed", { goal: format.number(proposed) })
                : t("marketplace:console.goalHint")
            }
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <TextField
            type="number"
            min={1}
            label={t("marketplace:console.cap")}
            value={cap}
            required
            onChange={(e) => setCap(e.target.value)}
          />
        </div>
      ) : null}
      <div className="ds-field">
        <label htmlFor={`reason-${project.id}-${move.label}`}>{t("marketplace:console.reason")}</label>
        <textarea
          id={`reason-${project.id}-${move.label}`}
          rows={3}
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </div>
      {confirmation ? (
        <p role="alert" className="project-admin__confirm">
          <Icon name="warning" size={16} />
          {t("marketplace:console.confirm", { project: project.title })}
        </p>
      ) : admin.isError ? (
        <p role="alert">{t("marketplace:console.failed")}</p>
      ) : null}
    </Dialog>
  );
}

function ProjectRow({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  return (
    <li className="project-card project-admin" data-state={project.state}>
      <div className="project-card__head">
        <span className="project-card__badge">
          <Icon name={STATE_ICON[project.state] ?? "lightbulb"} size={14} />
          {t(`marketplace:state.${project.state}`)}
        </span>
        <span className="project-admin__date">
          {t("marketplace:console.updated", { date: format.date(project.updated_at) })}
        </span>
      </div>
      <h2 className="project-card__title">
        <Link to={`/projects/${project.id}`}>{project.title}</Link>
      </h2>
      <Stepper state={project.state} />
      <Gathered project={project} />
      <div className="project-card__figures">
        <span>
          <Icon name="coins" size={16} />
          <strong>{format.number(project.totals.reserved + project.totals.consumed)}</strong>
          {t("marketplace:projects.gathered")}
        </span>
        <span>
          <Icon name="users" size={16} />
          {t("marketplace:projects.funders", { count: project.totals.funders })}
        </span>
      </div>
      {moves(project).length ? (
        <div className="project-admin__moves">
          {moves(project).map((move) => (
            <MoveButton key={move.label} project={project} move={move} />
          ))}
        </div>
      ) : null}
    </li>
  );
}

/**
 * Project console (spec 015 T014, ``projects.manage``; issue 303 redesign): the projects by what they wait
 * for — my decision first, then those running, then those over — each as a card with its way, what it
 * gathered and its decisions; each decision opens a window for its public reason, and asks again when it
 * moves members' Coins.
 */
export default function ProjectConsole() {
  const t = useT();
  const projects = useProjects();
  const list = projects.data ?? [];
  const count = (tab: string) => list.filter((p) => TABS[tab]?.includes(p.state)).length;
  const [chosen, setChosen] = useState<string | null>(null);
  const tab = chosen ?? (projects.isSuccess && !count("decide") ? "running" : "decide");
  const shown = list.filter((p) => TABS[tab]?.includes(p.state));
  return (
    <AdminPage
      icon="lightbulb"
      title={t("marketplace:console.title")}
      description={t("marketplace:console.description")}
    >
      <fieldset className="ds-subnav" aria-label={t("marketplace:projects.stages")}>
        {Object.keys(TABS).map((key) => (
          <button key={key} type="button" aria-pressed={tab === key} onClick={() => setChosen(key)}>
            {t(`marketplace:console.tab.${key}`)}
            <span className="admin-tabs__count">{count(key)}</span>
          </button>
        ))}
      </fieldset>
      {projects.isError ? <FunctionalState state="unavailable" onRetry={() => projects.refetch()} /> : null}
      {projects.isSuccess && !shown.length ? (
        <AdminEmpty icon="lightbulb" title={t("marketplace:console.empty")} />
      ) : (
        <ul className="project-grid">
          {shown.map((project) => (
            <ProjectRow key={project.id} project={project} />
          ))}
        </ul>
      )}
    </AdminPage>
  );
}
