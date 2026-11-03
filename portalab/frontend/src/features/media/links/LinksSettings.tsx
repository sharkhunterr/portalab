import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { SettingsCard, SettingsGrid, SettingsPage } from "../../account/SettingsKit";
import { connectorIcon } from "../../services/connectorIcons";
import { useLinkActions, useLinks } from "../api";
import "../media.css";

/**
 * Media accounts (spec 024 T022; #46 redrawn like the other « My account » tabs): the accounts linked on
 * media services — each with its service's name and icon and whether it is verified — then a card to link
 * another; activity is only attributed once the link is verified (through the service's code, or by an
 * administrator).
 */
interface Service {
  id: string;
  name: string;
  connector?: string | null;
}

export function useServices() {
  return useQuery({
    queryKey: ["services", "health", "names"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/services/health")).data as unknown as { items: Service[] }).items,
  });
}

export function LinksSettings() {
  const t = useT();
  const links = useLinks();
  const services = useServices();
  const { add, verify, remove } = useLinkActions();
  const [service, setService] = useState("");
  const [account, setAccount] = useState("");
  const [proofs, setProofs] = useState<Record<string, string>>({});
  const serviceOf = (id: string) => services.data?.find((s) => s.id === id);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(
      { service_id: service.trim(), external_user_id: account.trim() },
      { onSuccess: () => setAccount("") },
    );
  };
  const items = links.data ?? [];
  return (
    <SettingsPage icon="link" title={t("media:links.title")} lead={t("media:links.intro")}>
      {add.isError || verify.isError ? <FunctionalState state="error" /> : null}
      <SettingsGrid>
        <SettingsCard
          icon="link"
          title={t("account:media.linked")}
          hint={t("account:media.linkedHint", { count: items.length })}
        >
          {links.isPending ? <FunctionalState state="loading" /> : null}
          {links.data && items.length === 0 ? (
            <p className="settings-muted">{t("media:links.empty")}</p>
          ) : null}
          <ul className="settings-list">
            {items.map((link) => {
              const known = serviceOf(link.service_id);
              return (
                <li key={link.id}>
                  <span className="linked-service" aria-hidden="true">
                    <Icon name={connectorIcon(known?.connector)} size={18} />
                  </span>
                  <span className="settings-list__text">
                    <strong>{known?.name ?? t("account:media.service")}</strong>
                    <span>{t("account:media.as", { account: link.external_user_id })}</span>
                  </span>
                  <span className="settings-pill" data-tone={link.verified ? "ok" : "wait"}>
                    <Icon name={link.verified ? "check" : "clock"} size={12} />
                    {link.verified ? t("media:links.verified") : t("media:links.unverified")}
                  </span>
                  {link.verified ? null : (
                    <form
                      className="settings-fields"
                      onSubmit={(event) => {
                        event.preventDefault();
                        verify.mutate({ id: link.id, proof: proofs[link.id] ?? "" });
                      }}
                    >
                      <TextField
                        label={t("media:links.proof")}
                        value={proofs[link.id] ?? ""}
                        onChange={(e) => setProofs({ ...proofs, [link.id]: e.target.value })}
                      />
                      <Button type="submit" variant="secondary">
                        {t("media:links.verify")}
                      </Button>
                    </form>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="ds-button--quiet-danger"
                    onClick={() => remove.mutate(link.id)}
                    aria-label={`${t("media:links.remove")}: ${known?.name ?? ""} ${link.external_user_id}`}
                    title={t("media:links.remove")}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </li>
              );
            })}
          </ul>
        </SettingsCard>
        <SettingsCard icon="plus" title={t("account:media.add")} hint={t("account:media.addHint")}>
          <form onSubmit={submit}>
            <div className="settings-fields">
              {services.data?.length ? (
                <SelectField
                  label={t("media:links.service")}
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  required
                >
                  <option value="">{t("account:media.choose")}</option>
                  {services.data.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </SelectField>
              ) : (
                <TextField
                  label={t("media:links.service")}
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  required
                />
              )}
              <TextField
                label={t("media:links.account")}
                value={account}
                onChange={(e) => setAccount(e.target.value)}
                required
              />
            </div>
            <div className="settings-actions">
              <Button type="submit" disabled={add.isPending}>
                <Icon name="link" size={16} />
                {t("media:links.add")}
              </Button>
            </div>
          </form>
        </SettingsCard>
      </SettingsGrid>
    </SettingsPage>
  );
}

export default LinksSettings;
