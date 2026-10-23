import { useState } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { type CardPack, useOpenPack } from "./api";
import { CardBooster } from "./CardBooster";
import { MediaCardView } from "./MediaCardView";

/**
 * Issue 229: opening a pack — its cards were drawn when it was given; here they turn over one by one (a click
 * on the next), the rarest last, each in its version. Issue 234: shown as its booster, opened by a click on it.
 */
export function PackOpening({ pack, booster = false }: { pack: CardPack; booster?: boolean }) {
  const t = useT();
  const open = useOpenPack();
  const [shown, setShown] = useState(0);
  const [visible, setVisible] = useState(false);
  const order = { common: 0, rare: 1, epic: 2, legendary: 3 } as const;
  const cards = [...(open.data?.cards ?? [])].sort((a, b) => order[a.rarity] - order[b.rarity]);
  const done = cards.length > 0 && shown >= cards.length;
  return (
    <Dialog
      open={visible}
      onOpenChange={(next) => {
        setVisible(next);
        if (next && !open.data && !open.isPending) open.mutate(pack.id);
      }}
      size="lg"
      title={t("gamification:cards.pack.title", { name: pack.set_name ?? "" })}
      closeLabel={t("gamification:cards.close")}
      trigger={
        booster ? (
          <button
            type="button"
            className="cbooster-trigger"
            aria-label={`${t("gamification:cards.pack.open")} — ${pack.set_name ?? t("gamification:cards.pack.any")}`}
          >
            <CardBooster pack={pack} />
          </button>
        ) : (
          <Button>
            <Icon name="gift" size={16} />
            {t("gamification:cards.pack.open")}
          </Button>
        )
      }
    >
      <div className="cards-reveal">
        {open.isPending ? <p>{t("gamification:cards.pack.opening")}</p> : null}
        {open.isError ? <p role="alert">{t("gamification:cards.pack.failed")}</p> : null}
        {cards.map((card, index) => (
          <button
            key={card.copy ?? `${card.id}-${index}`}
            type="button"
            className="cards-reveal__slot"
            data-turned={index < shown || undefined}
            data-rarity={card.rarity}
            disabled={index !== shown}
            onClick={() => setShown(index + 1)}
            aria-label={index < shown ? card.name : t("gamification:cards.pack.turn")}
          >
            <span className="cards-reveal__back" aria-hidden="true">
              <Icon name="layers" size={36} />
            </span>
            <span className="cards-reveal__face">
              <MediaCardView card={card} variant={card.variant ?? "normal"} />
            </span>
          </button>
        ))}
      </div>
      <DialogActions>
        {done ? (
          <Button variant="secondary" onClick={() => setVisible(false)}>
            {t("gamification:cards.close")}
          </Button>
        ) : cards.length ? (
          <Button variant="secondary" onClick={() => setShown(cards.length)}>
            {t("gamification:cards.pack.all")}
          </Button>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
