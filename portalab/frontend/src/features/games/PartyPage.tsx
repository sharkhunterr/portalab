import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useParams, useSearchParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { Skeleton } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type PartyView, skewOf, useGamesHub, useOpenParty, useParty, usePartyAction } from "./api";
import { QuestionView, RevealView, useRemaining } from "./QuestionView";
import "./games.css";

/** Issue 265: open a party on a game (its rounds, its time; the host plays or only runs the screen). */
export function PartyHome() {
  const t = useT();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const hub = useGamesHub();
  const choices = (hub.data?.games ?? []).filter((g) => g.party);
  const [game, setGame] = useState(search.get("game") ?? "");
  const chosen = choices.find((g) => g.key === game) ?? choices[0];
  const [rounds, setRounds] = useState<string>("");
  const [seconds, setSeconds] = useState<string>("");
  const [hostPlays, setHostPlays] = useState(true);
  const [code, setCode] = useState("");
  const open = useOpenParty();
  return (
    <div className="games-page">
      <PageHeader
        title={t("gamification:games.party.title")}
        context={t("gamification:games.party.pitch")}
        icon="users"
      />
      {hub.isPending ? (
        <Skeleton shape="card" label={t("gamification:games.loading")} />
      ) : !hub.data?.party ? (
        <p className="games-muted">{t("gamification:games.party.off")}</p>
      ) : (
        <div className="games-party-home">
          <form
            className="games-panel"
            onSubmit={(event) => {
              event.preventDefault();
              if (!chosen) return;
              open.mutate(
                {
                  game: chosen.key,
                  rounds: rounds ? Number(rounds) : null,
                  seconds: seconds ? Number(seconds) : null,
                  host_plays: hostPlays,
                },
                { onSuccess: (view) => navigate(`/games/party/${view.code}`) },
              );
            }}
          >
            <h2>{t("gamification:games.party.open")}</h2>
            <SelectField
              label={t("gamification:games.party.game")}
              value={chosen?.key ?? ""}
              onChange={(e) => setGame(e.target.value)}
            >
              {choices.map((g) => (
                <option key={g.key} value={g.key}>
                  {t(`gamification:games.game.${g.key}.name`)}
                </option>
              ))}
            </SelectField>
            {chosen ? (
              <p className="games-muted">{t(`gamification:games.game.${chosen.key}.pitch`)}</p>
            ) : null}
            <div className="games-panel__row">
              <TextField
                label={t("gamification:games.party.rounds")}
                type="number"
                min={1}
                max={30}
                placeholder={String(chosen?.rounds ?? "")}
                value={rounds}
                onChange={(e) => setRounds(e.target.value)}
              />
              <TextField
                label={t("gamification:games.party.seconds")}
                type="number"
                min={5}
                max={180}
                placeholder={String(chosen?.seconds ?? "")}
                value={seconds}
                onChange={(e) => setSeconds(e.target.value)}
              />
            </div>
            <CheckboxField
              label={t("gamification:games.party.hostPlays")}
              hint={t("gamification:games.party.hostPlaysHint")}
              checked={hostPlays}
              onChange={(e) => setHostPlays(e.target.checked)}
            />
            <Button type="submit" disabled={!chosen || open.isPending}>
              <Icon name="party" size={16} />
              {t("gamification:games.party.open")}
            </Button>
            {open.error ? <p className="games-error">{open.error.message}</p> : null}
          </form>
          <form
            className="games-panel"
            onSubmit={(event) => {
              event.preventDefault();
              navigate(`/games/party/${code}?join=1`);
            }}
          >
            <h2>{t("gamification:games.party.join")}</h2>
            <TextField
              label={t("gamification:games.party.code")}
              value={code}
              maxLength={6}
              autoComplete="off"
              autoCapitalize="characters"
              onChange={(e) => setCode(e.target.value.replace(/[^a-zA-Z]/g, "").toUpperCase())}
            />
            <Button type="submit" disabled={code.length < 4}>
              {t("gamification:games.party.join")}
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}

function Players({ view, round }: { view: PartyView; round: boolean }) {
  const t = useT();
  const format = useFormat();
  return (
    <ol className="games-players">
      {view.players.map((player, at) => (
        <li
          key={player.id}
          data-me={player.me || undefined}
          data-answered={round && player.answered ? "true" : undefined}
        >
          <span className="games-players__rank">{player.rank ?? at + 1}</span>
          <span className="games-players__name">{player.name}</span>
          {round && view.phase === "question" ? (
            <span className="games-muted">
              {player.answered ? <Icon name="check" size={14} /> : <Icon name="hourglass" size={14} />}
            </span>
          ) : null}
          {player.points != null ? (
            <span className="games-players__points">+{format.number(player.points)}</span>
          ) : null}
          <b>{format.number(player.score)}</b>
        </li>
      ))}
      {!view.players.length ? <li className="games-muted">{t("gamification:games.party.nobody")}</li> : null}
    </ol>
  );
}

function Countdown({ view, skew }: { view: PartyView; skew: number }) {
  const { before } = useRemaining(view.started, view.settings.seconds, skew, true);
  if (before <= 0) return null;
  return <p className="games-countdown">{Math.ceil(before / 1000)}</p>;
}

function NextIn({ at, skew }: { at: string; skew: number }) {
  const t = useT();
  const { before } = useRemaining(at, 0, skew, true);
  return (
    <p className="games-muted">
      {t("gamification:games.party.nextIn", { seconds: Math.ceil(before / 1000) })}
    </p>
  );
}

/**
 * Issue 265: a party — its lobby (its code to share, who joined), its rounds (the same question for every
 * player at the same time, told live), the scores after each, its podium. ``?screen=1``: the party's screen
 * (a television), large and without answers.
 */
export default function PartyRoom() {
  const t = useT();
  const navigate = useNavigate();
  const { code = "" } = useParams();
  const [search] = useSearchParams();
  const screen = search.get("screen") === "1";
  const party = useParty(code);
  const act = usePartyAction(code);
  const view = party.data;
  const skew = useMemo(() => skewOf(view?.now), [view?.now]);
  const open = useOpenParty();
  const [copied, setCopied] = useState(false);
  // arriving with its code (``?join=1``) or a link: joined at once
  const wantsJoin = search.get("join") === "1";
  const missing = party.isError;
  // biome-ignore lint/correctness/useExhaustiveDependencies: once, when the party could not be read
  useEffect(() => {
    if (missing && wantsJoin && !act.isPending && !act.isSuccess) act.mutate({ kind: "join" });
  }, [missing, wantsJoin]);

  if (party.isPending || (missing && act.isPending))
    return <Skeleton shape="card" label={t("gamification:games.loading")} />;
  if (!view) {
    return (
      <div className="games-page">
        <PageHeader title={t("gamification:games.party.title")} icon="users" />
        <section className="games-panel">
          <p>{t("gamification:games.party.joinCode", { code })}</p>
          <Button disabled={act.isPending} onClick={() => act.mutate({ kind: "join" })}>
            {t("gamification:games.party.join")}
          </Button>
          {act.error ? <p className="games-error">{act.error.message}</p> : null}
          <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
        </section>
      </div>
    );
  }
  const link = `${window.location.origin}/games/party/${view.code}?join=1`;
  const round = view.status === "playing";
  return (
    <div className="games-page games-room" data-screen={screen || undefined}>
      <header className="games-room__head">
        <div>
          <p className="games-muted">{t(`gamification:games.game.${view.game}.name`)}</p>
          <h1
            className="games-room__code"
            aria-label={t("gamification:games.party.codeIs", { code: view.code })}
          >
            {view.code}
          </h1>
        </div>
        <div className="games-actions">
          {view.status === "lobby" ? (
            <Button
              variant="secondary"
              onClick={() => void navigator.clipboard?.writeText(link).then(() => setCopied(true))}
            >
              <Icon name="link" size={16} />
              {copied ? t("gamification:games.party.copied") : t("gamification:games.party.share")}
            </Button>
          ) : null}
          {view.is_host && !screen ? (
            <Button asChild variant="ghost">
              <RouterLink to={`/games/party/${view.code}?screen=1`} target="_blank">
                <Icon name="tv" size={16} />
                {t("gamification:games.party.screen")}
              </RouterLink>
            </Button>
          ) : null}
          {!screen && view.status !== "done" ? (
            <Button
              variant="ghost"
              onClick={() => act.mutate({ kind: "leave" }, { onSuccess: () => navigate("/games") })}
            >
              {view.is_host ? t("gamification:games.party.close") : t("gamification:games.party.leave")}
            </Button>
          ) : null}
        </div>
      </header>

      {view.status === "lobby" ? (
        <section className="games-lobby">
          <p>{t("gamification:games.party.waiting", { count: view.players.length })}</p>
          <Players view={view} round={false} />
          {view.is_host ? (
            <Button
              disabled={act.isPending || !view.players.length}
              onClick={() => act.mutate({ kind: "start" })}
            >
              <Icon name="play" size={16} />
              {t("gamification:games.party.start")}
            </Button>
          ) : (
            <p className="games-muted">
              {t("gamification:games.party.hostStarts", { host: view.host ?? "" })}
            </p>
          )}
        </section>
      ) : null}

      {round ? (
        <section className="games-round">
          <div className="games-status">
            <span>{t("gamification:games.round", { round: view.round ?? 1, rounds: view.rounds ?? 1 })}</span>
            {view.is_host ? (
              <Button
                variant="secondary"
                disabled={act.isPending}
                onClick={() => act.mutate({ kind: "next" })}
              >
                {view.phase === "question"
                  ? t("gamification:games.party.revealNow")
                  : t("gamification:games.next")}
                <Icon name="chevron-right" size={16} />
              </Button>
            ) : null}
          </div>
          <Countdown view={view} skew={skew} />
          {view.question ? (
            <QuestionView
              key={view.round}
              question={view.question}
              base={`/api/v1/games/parties/${view.code}`}
              started={view.started}
              seconds={view.settings.seconds}
              skew={skew}
              phase={view.phase ?? "question"}
              given={view.given ?? view.reveal?.mine?.given}
              answer={view.reveal?.answer}
              reveal={view.reveal?.reveal}
              mine={view.reveal?.mine}
              busy={act.isPending}
              screen={screen}
              onAnswer={view.playing && !screen ? (a) => act.mutate({ kind: "answer", ...a }) : undefined}
            />
          ) : null}
          {view.phase === "reveal" && view.reveal ? (
            <div className="games-after">
              <RevealView
                reveal={view.reveal.reveal}
                mine={view.reveal.mine}
                played={view.playing && !screen}
              />
              <NextIn at={view.reveal.next_at} skew={skew} />
            </div>
          ) : null}
          <Players view={view} round />
        </section>
      ) : null}

      {view.status === "done" ? (
        <section className="games-podium">
          <Icon name="trophy" size={48} />
          <h2>{t("gamification:games.party.over")}</h2>
          <ol className="games-podium__steps">
            {view.players.slice(0, 3).map((player) => (
              <li key={player.id} data-rank={player.rank ?? undefined}>
                <span className="games-podium__name">{player.name}</span>
                <b>{player.score}</b>
              </li>
            ))}
          </ol>
          <Players view={view} round={false} />
          <div className="games-actions">
            {view.is_host ? (
              <Button
                disabled={open.isPending}
                onClick={() =>
                  open.mutate(
                    {
                      game: view.game,
                      rounds: view.settings.rounds,
                      seconds: view.settings.seconds,
                      host_plays: view.settings.host_plays,
                    },
                    {
                      onSuccess: (next) => navigate(`/games/party/${next.code}${screen ? "?screen=1" : ""}`),
                    },
                  )
                }
              >
                <Icon name="retry" size={16} />
                {t("gamification:games.party.again")}
              </Button>
            ) : null}
            <Button asChild variant="secondary">
              <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
            </Button>
          </div>
        </section>
      ) : null}
      {view.status === "closed" ? (
        <p className="games-muted">{t("gamification:games.party.closed")}</p>
      ) : null}
      {act.error ? <p className="games-error">{act.error.message}</p> : null}
    </div>
  );
}
