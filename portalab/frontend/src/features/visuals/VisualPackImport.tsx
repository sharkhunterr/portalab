import { useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { ImportPanel } from "../extensions/ImportPanel";
import { useVisualAction, useVisualPacks } from "./api";
import { param } from "./parts";

/**
 * 028 (issue 138): importing a visual pack — the inbox read again, a .zip sent, a GitHub address, the updates
 * on offer. Shared by Extensions → Visual packs and → Widgets (a widget pack is a visual pack): an imported
 * version opens on the step it waits at.
 */
export function VisualPackImport({ widgets = false }: { widgets?: boolean }) {
  const t = useT();
  const navigate = useNavigate();
  const packs = useVisualPacks();
  const action = useVisualAction();
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [github, setGithub] = useState("");
  const [githubOpen, setGithubOpen] = useState(false);
  const [updates, setUpdates] = useState<Array<Record<string, unknown>> | null>(null);

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

  return (
    <ImportPanel
      title={t("admin:extensions.import")}
      description={t(widgets ? "admin:extensions.importWidgets" : "admin:extensions.importVisuals")}
      sources={[
        {
          key: "inbox",
          icon: "folder",
          label: t("admin:visuals.scan"),
          hint: packs.data?.inbox,
          render: ({ className, children }) => (
            <button
              type="button"
              className={className}
              title={packs.data?.inbox}
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
              {children}
            </button>
          ),
        },
        {
          key: "zip",
          icon: "inbox",
          label: t("admin:visuals.upload"),
          hint: t("admin:extensions.zipHint"),
          render: ({ className, children }) => (
            <label className={className}>
              <input
                className="ext-import__file"
                type="file"
                accept=".zip,application/zip"
                onChange={async (event) => {
                  const chosen = event.target.files?.[0];
                  event.target.value = "";
                  if (!chosen) return;
                  open(
                    await run(
                      `/api/v1/admin/visuals/upload?filename=${encodeURIComponent(chosen.name)}`,
                      undefined,
                      chosen,
                    ),
                  );
                }}
              />
              {children}
            </label>
          ),
        },
        {
          key: "github",
          icon: "link",
          label: t("admin:visuals.github"),
          hint: t("admin:extensions.githubHint"),
          render: ({ className, children }) => (
            <Dialog
              open={githubOpen}
              onOpenChange={setGithubOpen}
              title={t("admin:visuals.github")}
              description={t("admin:extensions.githubHelp")}
              closeLabel={t("admin:visuals.cancel")}
              trigger={
                <button type="button" className={className}>
                  {children}
                </button>
              }
            >
              <TextField
                label={t("admin:visuals.githubUrl")}
                value={github}
                onChange={(event) => setGithub(event.target.value)}
                placeholder="https://github.com/owner/repository"
              />
              <DialogActions>
                <Button
                  disabled={!github.trim() || action.isPending}
                  onClick={async () => {
                    const result = await run("/api/v1/admin/visuals/github", { url: github.trim() });
                    setGithubOpen(false);
                    open(result);
                  }}
                >
                  {t("admin:visuals.githubImport")}
                </Button>
              </DialogActions>
            </Dialog>
          ),
        },
        {
          key: "updates",
          icon: "sync",
          label: t("admin:visuals.checkUpdates"),
          hint: t("admin:extensions.updatesHint"),
          render: ({ className, children }) => (
            <button
              type="button"
              className={className}
              disabled={action.isPending}
              onClick={async () => {
                const result = await run("/api/v1/admin/visuals/updates");
                if (result) setUpdates((result.updates as Array<Record<string, unknown>>) ?? []);
              }}
            >
              {children}
            </button>
          ),
        },
      ]}
    >
      {message ? (
        message.tone === "error" ? (
          <FunctionalState state="error" label={message.text} />
        ) : (
          <p className="ext-import__result" role="status">
            {message.text}
          </p>
        )
      ) : null}
      {updates ? (
        <ul className="ext-import__found">
          {updates.length === 0 ? <li>{t("admin:visuals.noGithub")}</li> : null}
          {updates.map((u) => (
            <li key={String(u.pack)}>
              <strong>{String(u.pack)}</strong>
              <span>
                {u.error
                  ? String(u.error)
                  : u.update
                    ? t("admin:visuals.updateOffered", {
                        offered: param(u.offered),
                        installed: param(u.installed),
                      })
                    : t("admin:visuals.upToDate", { installed: param(u.installed) })}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </ImportPanel>
  );
}
