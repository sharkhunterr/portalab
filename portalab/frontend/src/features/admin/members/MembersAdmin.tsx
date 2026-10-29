import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import {
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTable,
  AdminTabs,
  AdminToolbar,
  FormActions,
  FormGrid,
  SearchBox,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Avatar } from "../../../design-system/components/Avatar";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import "../admin.css";
import { MemberEdit } from "./MemberEdit";
import { ServiceAccountsPanel } from "./ServiceAccountsPanel";

/**
 * Members (027 hubs; identity 002 admin API): every account with its state, creation and last sign-in,
 * searchable and filtered by state; invite a member (a verification link to share), resend it, suspend or
 * reactivate, ask for deletion (with the legal delay) or cancel it; edit a member (name, e-mail, roles,
 * linked service accounts). A second tab maps the accounts of the connected services to members. The server
 * enforces every right and protects the sole administrator. A member's name opens their card (``MemberCard``),
 * which reuses the list, the state and the actions below.
 */
export interface Member {
  id: string;
  login: string | null;
  display_name: string | null;
  state: string;
  created_at: string;
  last_sign_in_at: string | null;
  email?: string | null;
}

export const MEMBERS_KEY = ["admin", "members"] as const;
const KEY = MEMBERS_KEY;
export const STATE_TONE: Record<string, Tone> = {
  active: "ok",
  pending_verification: "info",
  inactive: "neutral",
  suspended: "warn",
  pending_deletion: "bad",
  deleted: "neutral",
};
const STATES = ["active", "pending_verification", "suspended", "inactive", "pending_deletion"] as const;

export async function allMembers(): Promise<Member[]> {
  const out: Member[] = [];
  let cursor: string | null = null;
  for (let page = 0; page < 40; page += 1) {
    const data = (
      await api.GET("/api/v1/users", { params: { query: { limit: 100, ...(cursor ? { cursor } : {}) } } })
    ).data as { items: Member[]; next_cursor: string | null } | undefined;
    out.push(...(data?.items ?? []));
    cursor = data?.next_cursor ?? null;
    if (!cursor) break;
  }
  return out;
}

function verifyLink(token: string): string {
  // issue 280: after « # » — the browser never sends it, so no server or proxy log keeps the token
  return `${window.location.origin}/verify#token=${encodeURIComponent(token)}`;
}

function InviteForm() {
  const t = useT();
  const client = useQueryClient();
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const invite = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/users", {
          body: { login, display_name: name || login, email: email || null },
        })
      ).data as { verification_token: string; expires_at: string },
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    invite.mutate();
  };
  if (invite.data) return <InviteLink token={invite.data.verification_token} />;
  return (
    <form onSubmit={submit} className="admin-form admin-dialog-body">
      <p className="admin-muted">{t("admin:members.inviteIntro")}</p>
      <FormGrid>
        <TextField
          label={t("admin:members.login")}
          required
          value={login}
          onChange={(e) => setLogin(e.target.value)}
        />
        <TextField label={t("admin:members.name")} value={name} onChange={(e) => setName(e.target.value)} />
        <TextField
          label={t("admin:members.email")}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </FormGrid>
      {invite.isError ? (
        <p role="alert" className="services-admin__ko">
          {invite.error instanceof ApiError ? invite.error.message : t("admin:members.refused")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={invite.isPending}>
          <Icon name="plus" size={16} />
          {t("admin:members.invite")}
        </Button>
      </FormActions>
    </form>
  );
}

export function InviteLink({ token }: { token: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const link = verifyLink(token);
  return (
    <div className="admin-form admin-dialog-body" role="status">
      <p className="services-admin__ok">{t("admin:members.invited")}</p>
      <TextField label={t("admin:members.link")} readOnly value={link} onFocus={(e) => e.target.select()} />
      <FormActions>
        <Button
          variant="secondary"
          onClick={() => {
            void navigator.clipboard?.writeText(link).then(() => setCopied(true));
          }}
        >
          <Icon name={copied ? "check" : "link"} size={16} />
          {copied ? t("admin:members.copied") : t("admin:members.copy")}
        </Button>
      </FormActions>
    </div>
  );
}

type Action = "suspend" | "reactivate" | "verification" | "deletion" | "cancel-deletion";

export function MemberActions({
  member,
  onLink,
  edit = true,
  suspensionOnly = false,
}: {
  member: Member;
  onLink: (token: string) => void;
  /** the « Edit » dialog — the member card edits inline instead */
  edit?: boolean;
  /** suspend / reactivate only (the card's « Vigilance » tab) */
  suspensionOnly?: boolean;
}) {
  const t = useT();
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const act = useMutation({
    mutationFn: async (action: Action) => {
      const params = { params: { path: { user_id: member.id } } };
      const body = { reason: "admin_action" };
      if (action === "suspend") return api.POST("/api/v1/users/{user_id}/suspend", { ...params, body });
      if (action === "reactivate") return api.POST("/api/v1/users/{user_id}/reactivate", { ...params, body });
      if (action === "deletion") return api.POST("/api/v1/users/{user_id}/deletion", { ...params, body });
      if (action === "cancel-deletion") return api.DELETE("/api/v1/users/{user_id}/deletion", params);
      const issued = (await api.POST("/api/v1/users/{user_id}/verification", params)).data as {
        verification_token: string;
      };
      onLink(issued.verification_token);
      return null;
    },
    onSuccess: () => {
      setConfirming(false);
      void client.invalidateQueries({ queryKey: KEY });
    },
  });
  const name = member.display_name ?? member.login ?? "";
  return (
    <>
      {edit ? (
        <Dialog
          size="lg"
          title={t("admin:members.editTitle", { name })}
          closeLabel={t("admin:services.close")}
          trigger={
            <Button variant="secondary" aria-label={`${t("admin:members.edit")} ${name}`}>
              {t("admin:members.edit")}
            </Button>
          }
        >
          <MemberEdit member={member} />
        </Dialog>
      ) : null}
      {act.isError ? (
        <span role="alert" className="admin-muted">
          {act.error instanceof ApiError ? act.error.message : t("admin:members.refused")}
        </span>
      ) : null}
      {member.state === "pending_verification" && !suspensionOnly ? (
        <Button
          variant="secondary"
          onClick={() => act.mutate("verification")}
          aria-label={`${t("admin:members.resend")} ${name}`}
        >
          <Icon name="link" size={16} />
          {t("admin:members.resend")}
        </Button>
      ) : null}
      {member.state === "active" || member.state === "inactive" ? (
        <Button
          variant="ghost"
          onClick={() => act.mutate("suspend")}
          aria-label={`${t("admin:members.suspend")} ${name}`}
        >
          {t("admin:members.suspend")}
        </Button>
      ) : null}
      {member.state === "suspended" ? (
        <Button
          variant="secondary"
          onClick={() => act.mutate("reactivate")}
          aria-label={`${t("admin:members.reactivate")} ${name}`}
        >
          {t("admin:members.reactivate")}
        </Button>
      ) : null}
      {suspensionOnly ? null : member.state === "pending_deletion" ? (
        <Button variant="ghost" onClick={() => act.mutate("cancel-deletion")}>
          {t("admin:members.cancelDeletion")}
        </Button>
      ) : member.state !== "deleted" ? (
        confirming ? (
          <Button variant="danger" onClick={() => act.mutate("deletion")}>
            {t("admin:members.confirmDeletion")}
          </Button>
        ) : (
          <Button
            variant="ghost"
            onClick={() => setConfirming(true)}
            aria-label={`${t("admin:members.delete")} ${name}`}
          >
            <Icon name="trash" size={16} />
          </Button>
        )
      ) : null}
    </>
  );
}

const TABS = ["members", "accounts"] as const;

export default function MembersAdmin() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "accounts" ? "accounts" : "members";
  return (
    <AdminPage
      icon="users"
      title={t("admin:members.title")}
      description={t("admin:members.subtitle")}
      primary={
        <Dialog
          title={t("admin:members.invite")}
          closeLabel={t("admin:services.close")}
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("admin:members.invite")}
            </Button>
          }
        >
          <InviteForm />
        </Dialog>
      }
      tabs={
        <AdminTabs
          label={t("admin:members.title")}
          current={tab}
          onChange={(next) => setParams(next === "members" ? {} : { tab: next }, { replace: true })}
          tabs={TABS.map((key) => ({ key, label: t(`admin:members.tabs.${key}`) }))}
        />
      }
    >
      {tab === "members" ? <MembersPanel /> : <ServiceAccountsPanel />}
    </AdminPage>
  );
}

function MembersPanel() {
  const t = useT();
  const format = useFormat();
  const members = useQuery({ queryKey: KEY, queryFn: allMembers });
  const [query, setQuery] = useState("");
  const [state, setState] = useState("all");
  const [link, setLink] = useState<string | null>(null);
  const all = members.data ?? [];
  const count = (s: string) => all.filter((m) => m.state === s).length;
  const needle = query.trim().toLowerCase();
  const shown = all.filter(
    (m) =>
      (state === "all" || m.state === state) &&
      (!needle || `${m.login ?? ""} ${m.display_name ?? ""} ${m.email ?? ""}`.toLowerCase().includes(needle)),
  );
  const ago = (iso: string | null) => (iso ? format.relative((Date.parse(iso) - Date.now()) / 1000) : "—");
  return (
    <>
      <AdminStats
        label={t("admin:members.title")}
        stats={[
          {
            key: "all",
            label: t("admin:members.stat.total"),
            value: format.number(all.length),
            icon: "users",
            tone: "info",
          },
          {
            key: "active",
            label: t("admin:members.state.active"),
            value: format.number(count("active")),
            icon: "check",
            tone: "ok",
          },
          {
            key: "pending",
            label: t("admin:members.state.pending_verification"),
            value: format.number(count("pending_verification")),
            icon: "clock",
            tone: count("pending_verification") ? "info" : "neutral",
          },
          {
            key: "suspended",
            label: t("admin:members.state.suspended"),
            value: format.number(count("suspended")),
            icon: "lock",
            tone: count("suspended") ? "warn" : "neutral",
          },
        ]}
      />
      {link ? (
        <AdminSection title={t("admin:members.link")} icon="link">
          <InviteLink token={link} />
        </AdminSection>
      ) : null}
      <AdminSection title={t("admin:members.list")} icon="users" flush>
        <div className="config-toolbar">
          <AdminToolbar>
            <SearchBox label={t("admin:members.search")} value={query} onChange={setQuery} />
          </AdminToolbar>
          <AdminTabs
            label={t("admin:members.list")}
            current={state}
            onChange={setState}
            tabs={[
              { key: "all", label: t("admin:members.all"), count: all.length },
              ...STATES.map((s) => ({ key: s, label: t(`admin:members.state.${s}`), count: count(s) })),
            ]}
          />
        </div>
        <AdminTable<Member>
          label={t("admin:members.list")}
          rows={shown}
          rowKey={(m) => m.id}
          empty={<p className="admin-muted admin-pad">{members.isPending ? "…" : t("admin:members.none")}</p>}
          columns={[
            {
              key: "who",
              header: t("admin:members.member"),
              primary: true,
              render: (m) => (
                <span className="member-cell">
                  <Avatar name={m.display_name ?? m.login ?? "?"} userId={m.id} size="sm" decorative />
                  <span className="services-admin__name">
                    <Link to={`/admin/members/${m.id}`} className="member-card__open">
                      <strong>{m.display_name ?? m.login}</strong>
                    </Link>
                    <span className="admin-muted">
                      @{m.login}
                      {m.email ? ` · ${m.email}` : ""}
                    </span>
                  </span>
                </span>
              ),
            },
            {
              key: "state",
              header: t("admin:members.stateColumn"),
              render: (m) => (
                <StatusBadge tone={STATE_TONE[m.state] ?? "neutral"}>
                  {t(`admin:members.state.${m.state}`)}
                </StatusBadge>
              ),
            },
            { key: "created", header: t("admin:members.created"), render: (m) => ago(m.created_at) },
            { key: "seen", header: t("admin:members.lastSeen"), render: (m) => ago(m.last_sign_in_at) },
          ]}
          actions={(m) => <MemberActions member={m} onLink={setLink} />}
        />
      </AdminSection>
    </>
  );
}
