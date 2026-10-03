import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMembers } from "../api";

/** ``/community/members`` (spec 012 T008): active members the viewer may see, searchable by name. */
export function Directory() {
  const t = useT();
  const format = useFormat();
  const [query, setQuery] = useState("");
  const members = useMembers(query.trim());
  const items = members.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section aria-labelledby="community-members" className="ds-stack">
      <h2 id="community-members">{t("community:members.title")}</h2>
      <TextField
        type="search"
        label={t("community:members.search")}
        value={query}
        maxLength={64}
        onChange={(event) => setQuery(event.target.value)}
      />
      {members.isError ? <FunctionalState state="unavailable" onRetry={() => members.refetch()} /> : null}
      {members.isSuccess && items.length === 0 ? (
        <p>
          {t("community:members.empty")}{" "}
          <Button variant="secondary" onClick={() => setQuery("")}>
            {t("community:members.emptyAction")}
          </Button>
        </p>
      ) : null}
      <ul className="community-members">
        {items.map((member) => (
          <li key={member.id} className="ds-card">
            <Link to={`/community/members/${member.id}`}>{member.display_name}</Link>
            <span className="community-meta">
              {t("community:members.joined", { date: format.date(member.joined_at) })}
            </span>
          </li>
        ))}
      </ul>
      {members.hasNextPage ? (
        <Button
          variant="secondary"
          onClick={() => members.fetchNextPage()}
          disabled={members.isFetchingNextPage}
        >
          {t("community:members.more")}
        </Button>
      ) : null}
    </section>
  );
}
