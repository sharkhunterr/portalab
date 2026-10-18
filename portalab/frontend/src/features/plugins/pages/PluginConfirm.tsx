import { type ReactNode, useCallback, useRef, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";

/** What Portalab's dialog states before a committing plugin action (spec 030, R6): bounded plain text. */
export interface ConfirmSummary {
  title: string;
  lines: string[];
  amount?: number;
  currency?: string;
}

interface Pending {
  summary: ConfirmSummary;
  token: string;
  path: string;
  body: Record<string, unknown>;
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}

export const CONFIRMATION_HEADER = "X-Portalab-Confirmation";

async function post(plugin: string, path: string, body: Record<string, unknown>, token?: string) {
  const headers: Record<string, string> = token ? { [CONFIRMATION_HEADER]: token } : {};
  // biome-ignore lint/suspicious/noExplicitAny: plugin routes are declared at runtime
  const result = await api.POST(`/api/v1/plugins/${plugin}/${path}` as any, { body: body as any, headers });
  return result.data as unknown;
}

function summaryOf(error: ApiError): ConfirmSummary | null {
  const raw = error.extensions.summary as Partial<ConfirmSummary> | undefined;
  if (!raw || typeof raw !== "object") return null;
  return {
    title: String(raw.title ?? ""),
    lines: Array.isArray(raw.lines) ? raw.lines.map(String) : [],
    ...(typeof raw.amount === "number"
      ? { amount: raw.amount, currency: String(raw.currency ?? "coins") }
      : {}),
  };
}

/** Thrown when the member cancels Portalab's confirmation (nothing was sent). */
export class Cancelled extends Error {
  constructor() {
    super("cancelled");
    this.name = "Cancelled";
  }
}

/**
 * 030: a plugin action, confirmed by Portalab when it is committing — the dialog is Portalab's own (a
 * protected surface no interface restyles), its words the exact content the server bound to the token.
 */
export function usePluginAction(plugin: string): {
  run: (path: string, body: Record<string, unknown>) => Promise<unknown>;
  dialog: ReactNode;
} {
  const t = useT();
  const format = useFormat();
  const [pending, setPending] = useState<Pending | null>(null);
  const settled = useRef(false);

  const run = useCallback(
    async (path: string, body: Record<string, unknown>) => {
      try {
        return await post(plugin, path, body);
      } catch (error) {
        if (!(error instanceof ApiError) || error.code !== "plugin.confirmation_required") throw error;
        const summary = summaryOf(error);
        const token = String(error.extensions.confirmation ?? "");
        if (!summary || !token) throw error;
        return await new Promise((resolve, reject) => {
          settled.current = false;
          setPending({ summary, token, path, body, resolve, reject });
        });
      }
    },
    [plugin],
  );

  const close = (open: boolean) => {
    if (open || !pending) return;
    if (!settled.current) pending.reject(new Cancelled());
    setPending(null);
  };

  const confirm = async () => {
    if (!pending) return;
    settled.current = true;
    const current = pending;
    setPending(null);
    try {
      current.resolve(await post(plugin, current.path, current.body, current.token));
    } catch (error) {
      current.reject(error);
    }
  };

  const dialog = pending ? (
    <Dialog
      trigger={<span hidden />}
      open
      onOpenChange={close}
      title={pending.summary.title || t("plugins:confirm.title")}
      closeLabel={t("plugins:confirm.cancel")}
    >
      <div className="ds-stack" data-plugin-confirm="">
        {pending.summary.lines.map((line, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the summary's lines have no other identity
          <p key={index}>{line}</p>
        ))}
        {pending.summary.amount !== undefined ? (
          <p>
            <strong>
              {t("plugins:confirm.amount", {
                amount: format.number(pending.summary.amount),
                currency: pending.summary.currency ?? "coins",
              })}
            </strong>
          </p>
        ) : null}
        <DialogActions>
          <Button onClick={confirm}>{t("plugins:confirm.confirm")}</Button>
        </DialogActions>
      </div>
    </Dialog>
  ) : null;

  return { run, dialog };
}
