import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import {
  AdminEmpty,
  AdminSection,
  AdminStats,
  AdminTable,
  AdminTabs,
  AdminToolbar,
  SearchBox,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import {
  ACCOUNTS_KEY,
  type AccountMember,
  accountLabel,
  memberLabel,
  type ServiceAccount,
  type ServiceAccounts,
  useServiceAccounts,
} from "./accounts";

/**
 * Service accounts ↔ members (027): every account of every connected service (Plex, Jellyfin, Seerr, RomM…)
 * and the member it belongs to. Unlinked accounts get a suggestion (same e-mail, else same name) to accept
 * one by one or all at once; any account can be pointed at a member by hand. Linking attributes the
 * account's past plays, requests and stats to the member.
 */
function useLink() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { service: string; account: string; user: string | null }) =>
      api.PUT("/api/v1/admin/media/accounts/{service_id}", {
        params: { path: { service_id: input.service } },
        body: { external_user_id: input.account, user_id: input.user },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  });
}

function MemberPicker({
  block,
  account,
  members,
}: {
  block: ServiceAccounts;
  account: ServiceAccount;
  members: AccountMember[];
}) {
  const t = useT();
  const link = useLink();
  const byId = new Map(members.map((m) => [m.id, m]));
  const suggested = account.suggestion ? byId.get(account.suggestion.user_id) : undefined;
  const label = `${t("admin:accounts.memberOf")} ${accountLabel(account)}`;
  return (
    <span className="accounts-picker">
      <select
        className="accounts-picker__select"
        aria-label={label}
        value={account.linked_user_id ?? ""}
        disabled={link.isPending}
        onChange={(e) =>
          link.mutate({
            service: block.service_id,
            account: account.external_id,
            user: e.target.value || null,
          })
        }
      >
        <option value="">{t("admin:accounts.unlinked")}</option>
        {members.map((m) => (
          <option key={m.id} value={m.id}>
            {memberLabel(m)}
            {m.login && m.login !== m.display_name ? ` (@${m.login})` : ""}
          </option>
        ))}
      </select>
      {!account.linked_user_id && suggested ? (
        <Button
          variant="secondary"
          disabled={link.isPending}
          onClick={() =>
            link.mutate({ service: block.service_id, account: account.external_id, user: suggested.id })
          }
          aria-label={`${t("admin:accounts.accept")} ${memberLabel(suggested)} — ${accountLabel(account)}`}
        >
          <Icon name="sparkles" size={16} />
          {memberLabel(suggested)}
          <span className="admin-muted">· {t(`admin:accounts.reason.${account.suggestion?.reason}`)}</span>
        </Button>
      ) : null}
      {link.isError ? (
        <span role="alert" className="admin-muted">
          {link.error instanceof ApiError ? link.error.message : t("admin:members.refused")}
        </span>
      ) : null}
    </span>
  );
}

function ServiceBlock({
  block,
  members,
  filter,
  needle,
}: {
  block: ServiceAccounts;
  members: AccountMember[];
  filter: string;
  needle: string;
}) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const apply = useMutation({
    mutationFn: async () =>
      api.POST("/api/v1/admin/media/accounts/apply-suggestions", { body: { service_id: block.service_id } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  });
  const suggestions = block.accounts.filter((a) => !a.linked_user_id && a.suggestion).length;
  const rows = block.accounts.filter(
    (a) =>
      (filter === "all" ||
        (filter === "linked" && a.linked_user_id) ||
        (filter === "unlinked" && !a.linked_user_id) ||
        (filter === "suggested" && !a.linked_user_id && a.suggestion)) &&
      (!needle ||
        `${a.username ?? ""} ${a.display_name ?? ""} ${a.email ?? ""}`.toLowerCase().includes(needle)),
  );
  const linked = block.accounts.filter((a) => a.linked_user_id).length;
  return (
    <AdminSection
      title={block.name}
      description={t("admin:accounts.linkedCount", { linked, count: block.accounts.length })}
      icon="server"
      flush
      actions={
        suggestions ? (
          <Button variant="secondary" disabled={apply.isPending} onClick={() => apply.mutate()}>
            <Icon name="sparkles" size={16} />
            {t("admin:accounts.applyService", { count: suggestions })}
          </Button>
        ) : null
      }
    >
      {!block.available ? (
        <p className="services-admin__ko admin-pad" role="alert">
          {t("admin:accounts.unavailable")}
        </p>
      ) : null}
      <AdminTable<ServiceAccount>
        label={`${t("admin:accounts.title")} — ${block.name}`}
        rows={rows}
        rowKey={(a) => a.external_id}
        empty={<p className="admin-muted admin-pad">{t("admin:accounts.noneMatch")}</p>}
        columns={[
          {
            key: "account",
            header: t("admin:accounts.account"),
            primary: true,
            render: (a) => (
              <span className="services-admin__name">
                <strong>{accountLabel(a)}</strong>
                <span className="admin-muted">
                  {[a.username && a.username !== a.display_name ? `@${a.username}` : null, a.email]
                    .filter(Boolean)
                    .join(" · ") || `#${a.external_id}`}
                </span>
              </span>
            ),
          },
          {
            key: "state",
            header: t("admin:accounts.state"),
            render: (a) =>
              a.linked_user_id ? (
                <StatusBadge tone="ok">{t("admin:accounts.linked")}</StatusBadge>
              ) : a.suggestion ? (
                <StatusBadge tone="info">{t("admin:accounts.suggested")}</StatusBadge>
              ) : (
                <StatusBadge tone="neutral">{t("admin:accounts.unlinked")}</StatusBadge>
              ),
          },
          {
            key: "activity",
            header: t("admin:accounts.activity"),
            render: (a) =>
              a.unlinked_sessions
                ? t("admin:accounts.waiting", {
                    count: a.unlinked_sessions,
                    n: format.number(a.unlinked_sessions),
                  })
                : "—",
          },
          {
            key: "member",
            header: t("admin:accounts.member"),
            render: (a) => <MemberPicker block={block} account={a} members={members} />,
          },
        ]}
      />
    </AdminSection>
  );
}

export function ServiceAccountsPanel() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const overview = useServiceAccounts();
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const applyAll = useMutation({
    mutationFn: async () => api.POST("/api/v1/admin/media/accounts/apply-suggestions", { body: {} }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ACCOUNTS_KEY }),
  });
  const services = overview.data?.services ?? [];
  const members = overview.data?.members ?? [];
  const accounts = services.flatMap((s) => s.accounts);
  const linked = accounts.filter((a) => a.linked_user_id).length;
  const suggested = accounts.filter((a) => !a.linked_user_id && a.suggestion).length;
  if (overview.isError) {
    return <AdminEmpty icon="lock" title={t("admin:accounts.forbidden")} />;
  }
  if (overview.isSuccess && !services.length) {
    return (
      <AdminEmpty
        icon="server"
        title={t("admin:accounts.noService")}
        action={<span className="admin-muted">{t("admin:accounts.noServiceHint")}</span>}
      />
    );
  }
  return (
    <>
      <AdminStats
        label={t("admin:accounts.title")}
        stats={[
          {
            key: "accounts",
            label: t("admin:accounts.stat.accounts"),
            value: format.number(accounts.length),
            icon: "server",
            tone: "info",
          },
          {
            key: "linked",
            label: t("admin:accounts.linked"),
            value: format.number(linked),
            icon: "link",
            tone: "ok",
          },
          {
            key: "suggested",
            label: t("admin:accounts.suggested"),
            value: format.number(suggested),
            icon: "sparkles",
            tone: suggested ? "info" : "neutral",
          },
          {
            key: "unlinked",
            label: t("admin:accounts.unlinked"),
            value: format.number(accounts.length - linked),
            icon: "user",
            tone: accounts.length - linked ? "warn" : "ok",
          },
        ]}
      />
      <div className="config-toolbar">
        <AdminToolbar>
          <SearchBox label={t("admin:accounts.search")} value={query} onChange={setQuery} />
          {suggested ? (
            <Button disabled={applyAll.isPending} onClick={() => applyAll.mutate()}>
              <Icon name="sparkles" size={16} />
              {t("admin:accounts.applyAll", { count: suggested })}
            </Button>
          ) : null}
        </AdminToolbar>
        <AdminTabs
          label={t("admin:accounts.title")}
          current={filter}
          onChange={setFilter}
          tabs={[
            { key: "all", label: t("admin:members.all"), count: accounts.length },
            { key: "suggested", label: t("admin:accounts.suggested"), count: suggested },
            { key: "unlinked", label: t("admin:accounts.unlinked"), count: accounts.length - linked },
            { key: "linked", label: t("admin:accounts.linked"), count: linked },
          ]}
        />
      </div>
      {applyAll.isSuccess ? (
        <p role="status" className="services-admin__ok">
          {t("admin:accounts.applied")}
        </p>
      ) : null}
      {services.map((block) => (
        <ServiceBlock
          key={block.service_id}
          block={block}
          members={members}
          filter={filter}
          needle={query.trim().toLowerCase()}
        />
      ))}
    </>
  );
}

/**
 * One member's service accounts (their card): per connected service, the accounts linked to them (unlink),
 * those suggested for them (accept) and any unlinked account to point at them — the same links as above.
 */
export function MemberServiceAccounts({ userId, name }: { userId: string; name: string }) {
  const t = useT();
  const overview = useServiceAccounts();
  const link = useLink();
  const services = overview.data?.services ?? [];
  if (overview.isError) return <AdminEmpty icon="lock" title={t("admin:accounts.forbidden")} />;
  if (overview.isSuccess && !services.length) {
    return (
      <AdminEmpty
        icon="server"
        title={t("admin:accounts.noService")}
        action={<span className="admin-muted">{t("admin:accounts.noServiceHint")}</span>}
      />
    );
  }
  return (
    <>
      {link.isError ? (
        <p role="alert" className="services-admin__ko">
          {link.error instanceof ApiError ? link.error.message : t("admin:members.refused")}
        </p>
      ) : null}
      {services.map((block) => {
        const linked = block.accounts.filter((a) => a.linked_user_id === userId);
        const suggested = block.accounts.filter((a) => !a.linked_user_id && a.suggestion?.user_id === userId);
        const free = block.accounts.filter((a) => !a.linked_user_id && a.suggestion?.user_id !== userId);
        const set = (account: ServiceAccount, user: string | null) =>
          link.mutate({ service: block.service_id, account: account.external_id, user });
        return (
          <AdminSection key={block.service_id} title={block.name} icon="server" flush>
            {!block.available ? (
              <p className="services-admin__ko admin-pad" role="alert">
                {t("admin:accounts.unavailable")}
              </p>
            ) : null}
            {linked.length || suggested.length ? (
              <ul className="admin-list">
                {linked.map((account) => (
                  <li key={account.external_id}>
                    <span className="admin-list__main">
                      <strong>{accountLabel(account)}</strong>
                      <StatusBadge tone="ok">{t("admin:accounts.linked")}</StatusBadge>
                    </span>
                    <Button
                      variant="ghost"
                      disabled={link.isPending}
                      onClick={() => set(account, null)}
                      aria-label={`${t("admin:accounts.unlink")} ${block.name} — ${accountLabel(account)}`}
                    >
                      {t("admin:accounts.unlink")}
                    </Button>
                  </li>
                ))}
                {suggested.map((account) => (
                  <li key={account.external_id}>
                    <span className="admin-list__main">
                      <strong>{accountLabel(account)}</strong>
                      <StatusBadge tone="info">
                        {t("admin:accounts.suggested")} ·{" "}
                        {t(`admin:accounts.reason.${account.suggestion?.reason}`)}
                      </StatusBadge>
                    </span>
                    <Button
                      variant="secondary"
                      disabled={link.isPending}
                      onClick={() => set(account, userId)}
                      aria-label={`${t("admin:accounts.accept")} ${name} — ${accountLabel(account)}`}
                    >
                      <Icon name="sparkles" size={16} />
                      {t("admin:accounts.accept")} {name}
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="admin-muted admin-pad">{t("admin:members.noLinked")}</p>
            )}
            {free.length ? (
              <div className="admin-pad member-card__link-account">
                <select
                  className="accounts-picker__select"
                  aria-label={`${t("admin:memberCard.linkAccount")} — ${block.name}`}
                  value=""
                  disabled={link.isPending}
                  onChange={(e) => {
                    const account = free.find((a) => a.external_id === e.target.value);
                    if (account) set(account, userId);
                  }}
                >
                  <option value="">{t("admin:memberCard.linkAccount")}</option>
                  {free.map((account) => (
                    <option key={account.external_id} value={account.external_id}>
                      {accountLabel(account)}
                      {account.email ? ` · ${account.email}` : ""}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </AdminSection>
        );
      })}
    </>
  );
}
