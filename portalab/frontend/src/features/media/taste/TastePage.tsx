import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField } from "../../../design-system/components/Field";
import { Dialog, DialogActions } from "../../../design-system/components/Overlays";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { Skeleton } from "../../../design-system/components/Placeholders";
import { Tabs } from "../../../design-system/components/Tabs";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useShellPreference } from "../../../shell/preferences";
import {
  type TasteTrait,
  useForgetTaste,
  useRecommendations,
  useTasteList,
  useTasteProfile,
  type Verdict,
} from "./api";
import { TasteDeck } from "./TasteDeck";
import { TasteRail } from "./TasteRail";
import "../media.css";
import "./taste.css";

const KINDS = ["all", "movie", "series", "book", "audiobook"] as const;
const LISTS: Verdict[] = ["later", "like", "dislike", "seen"];

function Traits({ title, traits }: { title: string; traits: TasteTrait[] }) {
  const t = useT();
  const format = useFormat();
  if (!traits.length) return null;
  return (
    <section>
      <h3>{title}</h3>
      <ol>
        {traits.slice(0, 8).map((trait) => (
          <li
            key={`${trait.role}:${trait.name}`}
            className="media-taste-trait"
            title={format.list(trait.titles)}
          >
            <span className="media-taste-trait__name">
              <span>{trait.name}</span>
              <small>
                {trait.role === "genre" || trait.role === "keyword" || trait.role === "saga"
                  ? t("media:taste.works", { count: trait.works })
                  : t(`media:taste.role.${trait.role}`)}
              </small>
            </span>
            <span className="media-taste-trait__bar" aria-hidden="true">
              <span style={{ inlineSize: `${Math.max(6, Math.round(trait.weight * 100))}%` }} />
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function List({ verdict }: { verdict: Verdict }) {
  const t = useT();
  const list = useTasteList(verdict);
  if (list.isPending) return <Skeleton shape="tile" count={4} label={t(`media:taste.list.${verdict}`)} />;
  if (!list.data?.length) return <p className="media-muted">{t(`media:taste.list.${verdict}Empty`)}</p>;
  return <TasteRail items={list.data} label={t(`media:taste.list.${verdict}`)} />;
}

/** Issue 190: my taste — titles to judge, what it recommends, what it is made of, my lists and its use. */
export function TastePage() {
  const t = useT();
  const client = useQueryClient();
  const [kind, setKind] = useState<(typeof KINDS)[number]>("all");
  const recommended = useRecommendations(kind === "all" ? undefined : kind, 30);
  const profile = useTasteProfile();
  const forget = useForgetTaste();
  const [useHistory, setUseHistory] = useShellPreference<boolean>("media.taste.useHistory", true);
  const [asking, setAsking] = useState(false);
  const taste = profile.data;
  const said = Object.values(taste?.counts ?? {}).reduce((sum, n) => sum + (n ?? 0), 0);
  return (
    <div className="media-taste-page">
      <PageHeader level={2} title={t("media:taste.title")} context={t("media:taste.pitch")} />
      {taste ? (
        <p className="media-taste-page__summary">{t("media:taste.summary", { works: taste.works, said })}</p>
      ) : null}

      <section aria-labelledby="taste-deck" className="media-row">
        <header className="media-row__head">
          <h3 id="taste-deck">{t("media:taste.deck.title")}</h3>
        </header>
        <div className="media-taste-page__deck">
          <TasteDeck />
        </div>
      </section>

      <section aria-labelledby="taste-for-you" className="media-row">
        <header className="media-row__head">
          <h3 id="taste-for-you">{t("media:taste.forYou")}</h3>
          <fieldset className="media-taste-tabs" aria-label={t("media:taste.kind")}>
            {KINDS.map((value) => (
              <button
                key={value}
                type="button"
                className="media-taste__button"
                aria-pressed={kind === value}
                onClick={() => setKind(value)}
              >
                {value === "all" ? t("media:taste.allKinds") : t(`media:kind.${value}`)}
              </button>
            ))}
          </fieldset>
        </header>
        {recommended.isPending ? (
          <Skeleton shape="tile" count={6} label={t("media:taste.forYou")} />
        ) : recommended.data?.length ? (
          <TasteRail items={recommended.data} label={t("media:taste.forYou")} grid />
        ) : (
          <p className="media-muted">{t("media:taste.nothingYet")}</p>
        )}
      </section>

      {taste && (taste.genres.length || taste.people.length || taste.sagas.length) ? (
        <section aria-labelledby="taste-made" className="media-row">
          <header className="media-row__head">
            <h3 id="taste-made">{t("media:taste.made")}</h3>
          </header>
          <div className="media-taste-traits">
            <Traits title={t("media:taste.group.genres")} traits={taste.genres} />
            <Traits title={t("media:taste.group.people")} traits={taste.people} />
            <Traits title={t("media:taste.group.sagas")} traits={taste.sagas} />
            <Traits title={t("media:taste.group.themes")} traits={taste.themes} />
          </div>
          {taste.against.length ? (
            <>
              <h4>{t("media:taste.against")}</h4>
              <ul className="media-taste-against">
                {taste.against.map((trait) => (
                  <li key={`${trait.role}:${trait.name}`}>{trait.name}</li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}

      <section aria-labelledby="taste-lists" className="media-row">
        <header className="media-row__head">
          <h3 id="taste-lists">{t("media:taste.lists")}</h3>
        </header>
        <Tabs
          label={t("media:taste.lists")}
          items={LISTS.map((verdict) => ({
            value: verdict,
            label: t(`media:taste.list.${verdict}`),
            content: <List verdict={verdict} />,
          }))}
        />
      </section>

      <section aria-labelledby="taste-privacy" className="media-row">
        <header className="media-row__head">
          <h3 id="taste-privacy">{t("media:taste.privacy")}</h3>
        </header>
        <CheckboxField
          label={t("media:taste.useHistory")}
          hint={t("media:taste.useHistoryHint")}
          checked={useHistory}
          onChange={(event) => {
            setUseHistory(event.currentTarget.checked);
            window.setTimeout(() => void client.invalidateQueries({ queryKey: ["media", "taste"] }), 400);
          }}
        />
        <Dialog
          open={asking}
          onOpenChange={setAsking}
          title={t("media:taste.forget.title")}
          description={t("media:taste.forget.body", { said })}
          closeLabel={t("media:taste.forget.keep")}
          trigger={
            <Button variant="secondary" disabled={!said}>
              {t("media:taste.forget.action")}
            </Button>
          }
        >
          <DialogActions>
            <Button
              variant="danger"
              disabled={forget.isPending}
              onClick={() => forget.mutate(undefined, { onSuccess: () => setAsking(false) })}
            >
              {t("media:taste.forget.confirm")}
            </Button>
          </DialogActions>
        </Dialog>
      </section>
    </div>
  );
}

export default TastePage;
