import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { SettingsCard } from "../account/SettingsKit";
import "./accounts.css";

/** Issue 426: the member's own account in each game library (play sessions, saves and states go there). */
export type RetroAccount = components["schemas"]["RetroAccountOut"];
const KEY = ["retro", "accounts"];

export function useRetroAccounts() {
  return useQuery({
    queryKey: KEY,
    retry: false, // retro play switched off, or not allowed: no card
    staleTime: 30_000,
    queryFn: async () => (await api.GET("/api/v1/retro/accounts")).data ?? [],
  });
}

function useAccountActions() {
  const client = useQueryClient();
  const keep = (found: RetroAccount) =>
    client.setQueryData<RetroAccount[]>(KEY, (all) =>
      (all ?? []).map((a) => (a.service_id === found.service_id ? found : a)),
    );
  const path = (service: string) => ({ params: { path: { service_id: service } } });
  return {
    link: useMutation({
      mutationFn: async (service: string) =>
        (await api.POST("/api/v1/retro/accounts/{service_id}", path(service))).data,
      onSuccess: (found) => found && keep(found),
    }),
    check: useMutation({
      mutationFn: async (service: string) =>
        (await api.POST("/api/v1/retro/accounts/{service_id}/check", path(service))).data,
      onSuccess: (found) => found && keep(found),
    }),
    unlink: useMutation({
      mutationFn: async (service: string) => {
        await api.DELETE("/api/v1/retro/accounts/{service_id}", path(service));
      },
      onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
    }),
  };
}

/**
 * « My game library account » (issue 426): the member authorises Portalab on their own RomM account once —
 * a code approved in RomM — and their play sessions, saves and states go there, not to the service's.
 */
export function RetroAccounts() {
  const t = useT();
  const accounts = useRetroAccounts();
  const actions = useAccountActions();
  if (!accounts.data?.length) return null;
  return (
    <SettingsCard icon="joystick" title={t("retro:account.title")} hint={t("retro:account.hint")}>
      <ul className="settings-list">
        {accounts.data.map((account) => (
          <AccountRow key={account.service_id} account={account} actions={actions} />
        ))}
      </ul>
      {actions.link.isError || actions.check.isError ? (
        <p className="settings-muted" role="alert">
          {t("retro:account.failed")}
        </p>
      ) : null}
    </SettingsCard>
  );
}

function AccountRow({
  account,
  actions,
}: {
  account: RetroAccount;
  actions: ReturnType<typeof useAccountActions>;
}) {
  const t = useT();
  const format = useFormat();
  const pending = account.state === "pending";
  const service = account.service_id;
  const { check } = actions;

  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(() => check.mutate(service), Math.max(2, account.interval) * 1000);
    return () => window.clearInterval(timer);
  }, [pending, service, account.interval, check.mutate]);

  const name = account.service_name ?? "RomM";
  return (
    <li className="retro-account">
      <span className="linked-service" aria-hidden="true">
        <Icon name="joystick" size={18} />
      </span>
      <span className="settings-list__text">
        <strong>{name}</strong>
        <span>
          {account.state === "linked"
            ? t("retro:account.linked", { username: account.username ?? "?" })
            : account.state === "expired"
              ? t("retro:account.expired")
              : pending
                ? t("retro:account.pending")
                : t("retro:account.none")}
        </span>
        {account.state === "linked" && account.expires_at ? (
          <span>{t("retro:account.until", { when: format.date(account.expires_at) })}</span>
        ) : null}
      </span>
      <span
        className="settings-pill"
        data-tone={account.state === "linked" ? "ok" : pending ? "wait" : undefined}
      >
        <Icon name={account.state === "linked" ? "check" : pending ? "clock" : "link"} size={12} />
        {t(`retro:account.state.${account.state}`)}
      </span>
      {pending ? (
        <div className="retro-account__code" role="status">
          <span>{t("retro:account.code")}</span>
          <strong>{account.user_code}</strong>
          {account.approve_url ? (
            <a
              className="ds-button ds-button--primary"
              href={account.approve_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Icon name="external" size={16} />
              {t("retro:account.approve", { service: name })}
            </a>
          ) : (
            <span className="settings-muted">{t("retro:account.approveThere", { service: name })}</span>
          )}
        </div>
      ) : null}
      {account.state === "linked" ? (
        <Button
          variant="secondary"
          onClick={() => actions.unlink.mutate(service)}
          disabled={actions.unlink.isPending}
        >
          {t("retro:account.unlink")}
        </Button>
      ) : (
        <Button
          variant={pending ? "secondary" : "primary"}
          onClick={() => actions.link.mutate(service)}
          disabled={actions.link.isPending}
        >
          <Icon name="link" size={16} />
          {t(pending ? "retro:account.again" : "retro:account.authorise")}
        </Button>
      )}
    </li>
  );
}
