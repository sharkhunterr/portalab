import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { AdminPage, AdminSection, StatusBadge, type Tone } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { nextStep, type PackRow, packPath, useVisualAction, useVisualPacks, type VersionRow } from "./api";
import { nameOf, OutcomeBadge, param } from "./parts";
import "./visuals.css";

/**
 * 028: « Visual packs » — where every look comes in. Sources (the inbox folder read again, a .zip uploaded, a
 * GitHub address, the updates on offer), then every pack — Portalab's own and imported ones together — with
 * its state, its versions and where each one is in its six steps (Import, Analysis, Security, Test, Review,
 * Validation). A version opens on the step it waits at.
 */

const STATE_TONE: Record<string, Tone> = { enabled: "ok", disabled: "neutral", archived: "warn" };
const STEP_TONE: Record<string, Tone> = {
  imported: "neutral",
  analysed: "info",
  tested: "info",
  reviewed: "info",
  published: "ok",
  refused: "bad",
  superseded: "neutral",
  purged: "neutral",
};

export default function VisualsAdmin() {
  const t = useT();
  const navigate = useNavigate();
  const packs = useVisualPacks();
  const action = useVisualAction();
  const [github, setGithub] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [updates, setUpdates] = useState<Array<Record<string, unknown>> | null>(null);
  const [filter, setFilter] = useState<"all" | "builtin" | "imported">("all");
  const file = useRef<HTMLInputElement>(null);

  const run = async (path: string, body?: unknown, raw?: Blob) => {
    setMessage(null);
    try {
      return await action.mutateAsync({ path, body, ...(raw ? { raw } : {}) });
    } catch (error) {
      setMessage({ tone: "error", text: String((error as Error).message) });
      return null;
    }
  };
  const open = (result: Record<string, unknown> | null) => {
    if (result?.pack && result.version) navigate(`/admin/visuals/${result.pack}/${result.version}`);
  };

  const list = (packs.data?.packs ?? []).filter((pack) =>
    filter === "all" ? true : filter === "builtin" ? pack.builtin : !pack.builtin,
  );
  return (
    <AdminPage
      icon="sparkles"
      title={t("admin:visuals.title")}
      description={t("admin:visuals.description")}
      wide
    >
      {message ? (
        <FunctionalState state={message.tone === "error" ? "error" : "available"} label={message.text} />
      ) : null}
      <AdminSection
        title={t("admin:visuals.sources")}
        icon="download"
        description={t("admin:visuals.sourcesHelp")}
      >
        <div className="visuals-sources">
          <div className="visuals-source">
            <p className="visuals-source__title">
              <Icon name="folder" size={16} /> {t("admin:visuals.inbox")}
            </p>
            <code className="visuals-source__path">{packs.data?.inbox ?? "…"}</code>
            <Button
              disabled={action.isPending}
              onClick={async () => {
                const result = await run("/api/v1/admin/visuals/scan");
                if (!result) return;
                const found = (result.found as Array<Record<string, unknown>>) ?? [];
                setMessage({
                  tone: "ok",
                  text: t("admin:visuals.scanned", {
                    count: found.length,
                    fresh: found.filter((f) => f.new).length,
                  }),
                });
              }}
            >
              <Icon name="sync" size={16} /> {t("admin:visuals.scan")}
            </Button>
          </div>
          <div className="visuals-source">
            <p className="visuals-source__title">
              <Icon name="inbox" size={16} /> {t("admin:visuals.upload")}
            </p>
            <input
              ref={file}
              type="file"
              accept=".zip,application/zip"
              aria-label={t("admin:visuals.upload")}
              onChange={async (event) => {
                const chosen = event.target.files?.[0];
                if (!chosen) return;
                const result = await run(
                  `/api/v1/admin/visuals/upload?filename=${encodeURIComponent(chosen.name)}`,
                  undefined,
                  chosen,
                );
                if (file.current) file.current.value = "";
                open(result);
              }}
            />
          </div>
          <div className="visuals-source">
            <p className="visuals-source__title">
              <Icon name="link" size={16} /> {t("admin:visuals.github")}
            </p>
            <TextField
              label={t("admin:visuals.githubUrl")}
              value={github}
              onChange={(event) => setGithub(event.target.value)}
              placeholder="https://github.com/owner/repository"
            />
            <div className="ds-stack--row">
              <Button
                disabled={!github.trim() || action.isPending}
                onClick={async () => open(await run("/api/v1/admin/visuals/github", { url: github.trim() }))}
              >
                {t("admin:visuals.githubImport")}
              </Button>
              <Button
                variant="secondary"
                disabled={action.isPending}
                onClick={async () => {
                  const result = await run("/api/v1/admin/visuals/updates");
                  if (result) setUpdates((result.updates as Array<Record<string, unknown>>) ?? []);
                }}
              >
                {t("admin:visuals.checkUpdates")}
              </Button>
            </div>
            {updates ? (
              <ul className="visuals-updates">
                {updates.length === 0 ? <li>{t("admin:visuals.noGithub")}</li> : null}
                {updates.map((u) => (
                  <li key={String(u.pack)}>
                    <strong>{String(u.pack)}</strong>{" "}
                    {u.error
                      ? String(u.error)
                      : u.update
                        ? t("admin:visuals.updateOffered", {
                            offered: param(u.offered),
                            installed: param(u.installed),
                          })
                        : t("admin:visuals.upToDate", { installed: param(u.installed) })}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      </AdminSection>

      <AdminSection
        title={t("admin:visuals.packs")}
        icon="package"
        flush
        actions={
          <>
            {filter === "builtin" ? (
              <div className="ds-stack--row">
                <Button
                  variant="secondary"
                  disabled={action.isPending}
                  onClick={async () => {
                    const result = await run("/api/v1/admin/visuals/builtin/state", { state: "enabled" });
                    if (result)
                      setMessage({
                        tone: "ok",
                        text: t("admin:visuals.builtinChanged", {
                          count: (result.changed as string[]).length,
                        }),
                      });
                  }}
                >
                  <Icon name="play" size={16} /> {t("admin:visuals.builtinOn")}
                </Button>
                <Button
                  variant="ghost"
                  disabled={action.isPending}
                  onClick={async () => {
                    const result = await run("/api/v1/admin/visuals/builtin/state", { state: "disabled" });
                    if (result)
                      setMessage({
                        tone: "ok",
                        text: t("admin:visuals.builtinChanged", {
                          count: (result.changed as string[]).length,
                        }),
                      });
                  }}
                >
                  <Icon name="pause" size={16} /> {t("admin:visuals.builtinOff")}
                </Button>
              </div>
            ) : null}
            <fieldset className="visuals-filter">
              <legend className="visually-hidden">{t("admin:visuals.filter")}</legend>
              {(["all", "builtin", "imported"] as const).map((value) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="visuals-filter"
                    checked={filter === value}
                    onChange={() => setFilter(value)}
                  />
                  {t(`admin:visuals.filters.${value}`)}
                </label>
              ))}
            </fieldset>
          </>
        }
      >
        {packs.isPending ? <FunctionalState state="loading" label={t("admin:visuals.loading")} /> : null}
        {list.length === 0 && !packs.isPending ? (
          <p className="visuals-empty">{t("admin:visuals.none")}</p>
        ) : null}
        <ul className="visuals-packs">
          {list.map((pack) => (
            <PackItem key={pack.id} pack={pack} run={run} busy={action.isPending} />
          ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}

function PackItem({
  pack,
  run,
  busy,
}: {
  pack: PackRow;
  run: (path: string, body?: unknown) => Promise<Record<string, unknown> | null>;
  busy: boolean;
}) {
  const t = useT();
  const latest = pack.versions[0];
  const name = nameOf(pack.names, pack.id);
  const [removing, setRemoving] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);
  const live = pack.state === "enabled";
  return (
    <li className="visuals-pack" data-state={pack.state}>
      <div className="visuals-pack__head">
        <div>
          <p className="visuals-pack__name">{name}</p>
          <p className="visuals-pack__meta">
            <code>{pack.id}</code> ·{" "}
            {pack.builtin
              ? t("admin:visuals.builtin")
              : t(`admin:visuals.source.${pack.source?.kind ?? "inbox"}`)}
            {pack.source?.url ? ` · ${pack.source.url}` : ""}
            {latest?.author ? ` · ${latest.author}` : ""}
            {latest?.license ? ` · ${latest.license}` : ""}
          </p>
        </div>
        <div className="visuals-pack__state">
          {pack.current ? (
            <StatusBadge tone={STATE_TONE[pack.state] ?? "neutral"}>
              {t(`admin:visuals.state.${pack.state}`, { version: pack.current })}
            </StatusBadge>
          ) : (
            <StatusBadge tone="neutral">{t("admin:visuals.unpublished")}</StatusBadge>
          )}
          {pack.socle ? <StatusBadge tone="info">{t("admin:visuals.socle")}</StatusBadge> : null}
          {pack.update && pack.remote ? (
            <StatusBadge tone="info">
              {t("admin:visuals.remote", { version: pack.remote.version })}
            </StatusBadge>
          ) : null}
          {pack.current && !pack.socle ? (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => run(`${packPath(pack.id)}/state`, { state: live ? "disabled" : "enabled" })}
            >
              <Icon name={live ? "pause" : "play"} size={16} />
              {live ? t("admin:visuals.switchOff") : t("admin:visuals.switchOn")}
            </Button>
          ) : null}
          {!pack.socle ? (
            <Dialog
              open={removing}
              onOpenChange={setRemoving}
              title={t("admin:visuals.removeTitle", { pack: name })}
              description={t("admin:visuals.removeHelp")}
              closeLabel={t("admin:visuals.cancel")}
              trigger={
                <Button variant="ghost" disabled={busy}>
                  <Icon name="trash" size={16} /> {t("admin:visuals.remove")}
                </Button>
              }
            >
              <DialogActions>
                <Button
                  variant="danger"
                  onClick={async () => {
                    const result = await run(`${packPath(pack.id)}/remove`);
                    setRemoving(false);
                    if (result)
                      setOutcome(
                        result.outcome === "archived"
                          ? t("admin:visuals.archived", { count: Number(result.owners) || 0 })
                          : t("admin:visuals.removed"),
                      );
                  }}
                >
                  {t("admin:visuals.remove")}
                </Button>
              </DialogActions>
            </Dialog>
          ) : null}
        </div>
      </div>
      {outcome ? <p className="visuals-pack__outcome">{outcome}</p> : null}
      <ul className="visuals-versions">
        {pack.versions.map((v) => (
          <VersionItem key={v.version} pack={pack} version={v} run={run} busy={busy} />
        ))}
      </ul>
    </li>
  );
}

function VersionItem({
  pack,
  version: v,
  run,
  busy,
}: {
  pack: PackRow;
  version: VersionRow;
  run: (path: string, body?: unknown) => Promise<Record<string, unknown> | null>;
  busy: boolean;
}) {
  const t = useT();
  const waiting = nextStep(v);
  const outcome =
    v.step === "published" || v.step === "superseded"
      ? "done"
      : v.outcomes.analysis === "blocking" || v.outcomes.security === "blocking"
        ? "blocking"
        : v.outcomes.analysis === "warning" || v.outcomes.security === "warning"
          ? "warning"
          : "todo";
  return (
    <li data-current={pack.current === v.version || undefined}>
      <Link className="visuals-version" to={`/admin/visuals/${pack.id}/${v.version}`}>
        <span className="visuals-version__number">{v.version}</span>
        <StatusBadge tone={STEP_TONE[v.step] ?? "neutral"}>
          {t(`admin:visuals.versionStep.${v.step}`)}
        </StatusBadge>
        {v.step !== "published" && v.step !== "superseded" && v.step !== "refused" ? (
          <span className="visuals-version__next">
            <OutcomeBadge outcome={outcome} /> {t(`admin:visuals.step.${waiting}`)}
          </span>
        ) : null}
        {v.summary ? (
          <span className="visuals-version__flags">
            {t("admin:visuals.elements", { count: v.summary.elements })}
            {v.summary.hd ? (
              <span className="visuals-flag" data-flag="hd">
                HD
              </span>
            ) : null}
            {v.summary.script ? (
              <span className="visuals-flag" data-flag="script">
                {t("admin:visuals.script")}
              </span>
            ) : null}
          </span>
        ) : null}
      </Link>
      {v.ever_published && pack.current !== v.version && !pack.builtin ? (
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => run(`${packPath(pack.id, v.version)}/rollback`)}
        >
          {t("admin:visuals.rollback")}
        </Button>
      ) : null}
      {!v.ever_published && !pack.builtin ? (
        <Button variant="ghost" disabled={busy} onClick={() => run(`${packPath(pack.id, v.version)}/purge`)}>
          {t("admin:visuals.purge")}
        </Button>
      ) : null}
    </li>
  );
}
