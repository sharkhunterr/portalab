import { useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { EmptyState, Skeleton } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMembers } from "../api";
import { MemberAvatar, MemberName } from "../MemberFace";

/** ``/community/members`` (spec 012 T008; 027 redesign): the active members the viewer may see, as cards
 * with their avatar, searchable by name. Issue 347: the anonymous members close the list, without name,
 * avatar, date nor profile (never in a search). */
export function Directory() {
  const t = useT();
  const format = useFormat();
  const [query, setQuery] = useState("");
  const members = useMembers(query.trim());
  const items = members.data?.pages.flatMap((page) => page.items) ?? [];
  const anonymous = members.hasNextPage ? 0 : (members.data?.pages.at(-1)?.anonymous ?? 0);
  return (
    <section aria-label={t("community:members.title")} className="ds-stack">
      <label className="community-search">
        <Icon name="search" size={18} />
        <span className="visually-hidden">{t("community:members.search")}</span>
        <input
          type="search"
          value={query}
          maxLength={64}
          placeholder={t("community:members.search")}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {members.isPending ? <Skeleton shape="tile" count={4} label={t("community:members.title")} /> : null}
      {members.isError ? <FunctionalState state="unavailable" onRetry={() => members.refetch()} /> : null}
      {members.isSuccess && items.length === 0 && anonymous === 0 ? (
        <EmptyState
          icon="users"
          title={t("community:members.empty")}
          action={
            <Button variant="secondary" onClick={() => setQuery("")}>
              {t("community:members.emptyAction")}
            </Button>
          }
        />
      ) : null}
      <ul className="community-members">
        {items.map((member) => (
          <li key={member.id}>
            <Link to={`/community/members/${member.id}`} className="community-member">
              <MemberAvatar id={member.id} name={member.display_name} look={member.look} size="lg" />
              <strong>
                <MemberName name={member.display_name} look={member.look} />
              </strong>
              <span className="community-meta">
                {t("community:members.joined", { date: format.date(member.joined_at) })}
              </span>
            </Link>
          </li>
        ))}
        {Array.from({ length: anonymous }, (_, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: anonymous members have nothing else to tell them apart
          <li key={`anonymous-${index}`}>
            <span className="community-member" data-anonymous="true">
              <span className="community-member__ghost" aria-hidden="true">
                <Icon name="user" size={28} />
              </span>
              <em>{t("gamification:leaderboard.anonymous")}</em>
              <span className="community-meta">{t("community:members.anonymousHint")}</span>
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
