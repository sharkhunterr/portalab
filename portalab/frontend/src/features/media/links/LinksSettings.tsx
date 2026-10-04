import { type FormEvent, useId, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useLinkActions, useLinks } from "../api";
import "../media.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/**
 * Media accounts (spec 024 T022): link an account on a media service; activity is only attributed once the
 * link is verified (through the service's code, or by an administrator).
 */
export function LinksSettings() {
  const t = useT();
  const headingId = useId();
  const links = useLinks();
  const { add, verify, remove } = useLinkActions();
  const [service, setService] = useState("");
  const [account, setAccount] = useState("");
  const [proofs, setProofs] = useState<Record<string, string>>({});
  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(
      { service_id: service.trim(), external_user_id: account.trim() },
      { onSuccess: () => setAccount("") },
    );
  };
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="film" title={t("media:links.title")} />
      <p>{t("media:links.intro")}</p>
      {links.isPending ? <FunctionalState state="loading" /> : null}
      {links.data && links.data.length === 0 ? <p>{t("media:links.empty")}</p> : null}
      <ul className="media-list">
        {(links.data ?? []).map((link) => (
          <li key={link.id}>
            <strong>{link.external_user_id}</strong> ·{" "}
            {link.verified ? t("media:links.verified") : t("media:links.unverified")}
            {link.verified ? null : (
              <form
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
            <Button variant="danger" onClick={() => remove.mutate(link.id)}>
              {t("media:links.remove")}
              <span className="visually-hidden">: {link.external_user_id}</span>
            </Button>
          </li>
        ))}
      </ul>
      <form onSubmit={submit}>
        <TextField
          label={t("media:links.service")}
          value={service}
          onChange={(e) => setService(e.target.value)}
          required
        />
        <TextField
          label={t("media:links.account")}
          value={account}
          onChange={(e) => setAccount(e.target.value)}
          required
        />
        <Button type="submit">{t("media:links.add")}</Button>
      </form>
      {add.isError || verify.isError ? <FunctionalState state="error" /> : null}
    </section>
  );
}

export default LinksSettings;
