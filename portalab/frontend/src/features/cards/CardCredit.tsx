import { useT } from "../../i18n/hooks/useT";

/** Issue 231: the characters' images come in part from TheTVDB, which asks to be named and linked. */
export function CardCredit() {
  const t = useT();
  return (
    <p className="cards-credit">
      {t("gamification:cards.credit")}{" "}
      <a href="https://thetvdb.com" target="_blank" rel="noreferrer noopener">
        TheTVDB
      </a>
    </p>
  );
}
