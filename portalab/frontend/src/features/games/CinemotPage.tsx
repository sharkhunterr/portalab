import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { Skeleton } from "../../design-system/components/Placeholders";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { type CinemotView, metadataImage, useCinemot, useGuess } from "./api";
import { Board } from "./Boards";
import "./games.css";

const AZERTY = ["AZERTYUIOP", "QSDFGHJKLM", "WXCVBN"];
const QWERTY = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"];
const MARK = { c: "right", p: "elsewhere", a: "absent" } as const;

/** The letters of a guess laid over the title's words (its spaces kept). */
function Row({ pattern, letters, marks }: { pattern: number[]; letters: string; marks?: string }) {
  let at = 0;
  return (
    <div className="games-cinemot__row">
      {pattern.map((size, word) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: the title's words in order
        <span key={word} className="games-cinemot__word">
          {Array.from({ length: size }, () => {
            const index = at++;
            const mark = marks?.[index] as keyof typeof MARK | undefined;
            return (
              <span key={index} className="games-cinemot__cell" data-mark={mark ? MARK[mark] : undefined}>
                {letters[index] ?? ""}
              </span>
            );
          })}
        </span>
      ))}
    </div>
  );
}

/** What each key was told: right somewhere, elsewhere, absent (the best told). */
function keyMarks(view: CinemotView): Record<string, string> {
  const rank = { right: 3, elsewhere: 2, absent: 1 } as Record<string, number>;
  const out: Record<string, string> = {};
  for (const guess of view.guesses) {
    [...guess.letters].forEach((letter, at) => {
      const mark = MARK[guess.marks[at] as keyof typeof MARK];
      if ((rank[mark] ?? 0) > (rank[out[letter] ?? ""] ?? 0)) out[letter] = mark;
    });
  }
  return out;
}

function share(view: CinemotView): string {
  const square = { c: "🟩", p: "🟨", a: "⬛" } as Record<string, string>;
  const rows = view.guesses.map((g) => [...g.marks].map((m) => square[m]).join(""));
  return `Ciné-mot ${view.day} ${view.won ? view.guesses.length : "X"}/${view.tries}\n${rows.join("\n")}`;
}

/**
 * Issue 265: the day's title to find — a film or a series of the library, the same for everyone today:
 * letters typed (on the page's keyboard or one's own), each told right, elsewhere or absent.
 */
export default function CinemotPage() {
  const t = useT();
  const { language } = useLocaleContext();
  const today = useCinemot();
  const guess = useGuess();
  const [typed, setTyped] = useState("");
  const [copied, setCopied] = useState(false);
  const view = today.data;
  const size = view ? view.pattern.reduce((a, b) => a + b, 0) : 0;
  const playing = view?.status === "playing";
  const press = useCallback(
    (key: string) => {
      if (!playing || guess.isPending) return;
      if (key === "Enter") {
        if (typed.length === size) guess.mutate(typed, { onSuccess: () => setTyped("") });
      } else if (key === "Backspace") setTyped((s) => s.slice(0, -1));
      else if (/^[a-zA-Z]$/.test(key)) setTyped((s) => (s.length < size ? s + key.toUpperCase() : s));
    },
    [playing, guess, typed, size],
  );
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if ((event.target as HTMLElement | null)?.closest("input, textarea")) return;
      press(event.key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [press]);
  const rows = language.startsWith("fr") ? AZERTY : QWERTY;
  const marks = view ? keyMarks(view) : {};
  return (
    <div className="games-page">
      <PageHeader
        title={t("gamification:games.game.cinemot.name")}
        context={t("gamification:games.game.cinemot.pitch")}
        icon="type"
      />
      {today.isPending ? (
        <Skeleton shape="card" label={t("gamification:games.loading")} />
      ) : !view ? (
        <p className="games-error">{today.error?.message ?? t("gamification:games.gone")}</p>
      ) : (
        <section className="games-cinemot">
          <p className="games-cinemot__hints">
            {view.hints.kind ? <span>{t(`media:kind.${view.hints.kind}`)}</span> : null}
            {view.hints.year ? <span>{view.hints.year}</span> : null}
            {(view.hints.genres ?? []).map((genre) => (
              <span key={genre}>{genre}</span>
            ))}
          </p>
          <div className="games-cinemot__grid">
            {view.guesses.map((g, at) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: the guesses in order
              <Row key={at} pattern={view.pattern} letters={g.letters} marks={g.marks} />
            ))}
            {playing ? <Row pattern={view.pattern} letters={typed} /> : null}
            {Array.from(
              { length: Math.max(0, view.tries - view.guesses.length - (playing ? 1 : 0)) },
              (_, at) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: the tries left
                <Row key={`left${at}`} pattern={view.pattern} letters="" />
              ),
            )}
          </div>
          {guess.error ? <p className="games-error">{guess.error.message}</p> : null}
          {playing ? (
            <div className="games-keyboard">
              {rows.map((row, at) => (
                <div key={row}>
                  {at === rows.length - 1 ? (
                    <button type="button" className="games-key" data-wide onClick={() => press("Enter")}>
                      {t("gamification:games.cinemot.enter")}
                    </button>
                  ) : null}
                  {[...row].map((letter) => (
                    <button
                      key={letter}
                      type="button"
                      className="games-key"
                      data-mark={marks[letter]}
                      onClick={() => press(letter)}
                    >
                      {letter}
                    </button>
                  ))}
                  {at === rows.length - 1 ? (
                    <button
                      type="button"
                      className="games-key"
                      data-wide
                      aria-label={t("gamification:games.cinemot.erase")}
                      onClick={() => press("Backspace")}
                    >
                      <Icon name="back" size={16} />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="games-over">
              <h2>
                {view.won
                  ? t("gamification:games.cinemot.won", { tries: view.guesses.length })
                  : t("gamification:games.cinemot.lost")}
              </h2>
              {view.answer ? (
                <div className="games-reveal__title">
                  {view.answer.poster ? (
                    <img src={metadataImage(view.answer.poster, "w185") ?? ""} alt="" />
                  ) : null}
                  <span>
                    {view.answer.title}
                    {view.answer.year ? ` (${view.answer.year})` : ""}
                  </span>
                </div>
              ) : null}
              {view.won ? <p>{t("gamification:games.score", { score: view.score })}</p> : null}
              <div className="games-actions">
                <Button
                  variant="secondary"
                  onClick={() => {
                    void navigator.clipboard?.writeText(share(view)).then(() => setCopied(true));
                  }}
                >
                  <Icon name="copy" size={16} />
                  {copied ? t("gamification:games.cinemot.copied") : t("gamification:games.cinemot.share")}
                </Button>
                <Button asChild>
                  <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
                </Button>
              </div>
              <p className="games-muted">{t("gamification:games.cinemot.tomorrow")}</p>
            </div>
          )}
          <Board game="cinemot" />
        </section>
      )}
    </div>
  );
}
