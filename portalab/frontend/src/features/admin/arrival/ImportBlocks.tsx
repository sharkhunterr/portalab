import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { BLOCK_ICONS, neededBy, type OfferedBlock, toggled } from "./importBlocks";
import "./arrival.css";

/**
 * Issue 392 — the arrival wizard's « what to bring »: the archive's blocks as cards to tick (what one needs
 * comes with it and says why, what needs it goes with it). The Admin's account always comes; without the
 * members, what they made is handed to the Admin and what was theirs stays out.
 */
export function ImportBlocks({
  blocks,
  chosen,
  onChange,
  disabled = false,
}: {
  blocks: readonly OfferedBlock[];
  chosen: ReadonlySet<string>;
  onChange: (next: Set<string>) => void;
  disabled?: boolean;
}) {
  const t = useT();
  const name = (key: string) => t(`account:arrival.import.block.${key}.title`);
  return (
    <fieldset className="features-picker import-blocks">
      <legend>{t("account:arrival.import.choose.title")}</legend>
      <p className="arrival__lead">{t("account:arrival.import.choose.lead")}</p>
      <ul>
        {blocks.map((block) => {
          const on = chosen.has(block.key);
          const id = `import-block-${block.key}`;
          const needing = neededBy(blocks, chosen, block.key);
          const counts = Object.entries(block.counts)
            .filter(([, count]) => count > 0)
            .map(([label, count]) => t(`account:arrival.import.blockCount.${label}`, { count }));
          return (
            <li key={block.key} data-on={on || undefined}>
              <input
                id={id}
                type="checkbox"
                className="features-picker__check"
                checked={on}
                disabled={disabled}
                aria-describedby={`${id}-hint`}
                onChange={(e) => onChange(toggled(blocks, chosen, block.key, e.target.checked))}
              />
              <label htmlFor={id} className="features-picker__card">
                <span className="features-picker__icon" aria-hidden="true">
                  <Icon name={BLOCK_ICONS[block.key] ?? "package"} size={20} />
                </span>
                <span className="features-picker__text">
                  <strong>{name(block.key)}</strong>
                  <span id={`${id}-hint`}>
                    {t(`account:arrival.import.block.${block.key}.hint`)}
                    {counts.length ? ` · ${counts.join(", ")}` : ""}
                    {needing.length
                      ? ` · ${t("account:arrival.import.choose.needed", { blocks: needing.map(name).join(", ") })}`
                      : ""}
                  </span>
                </span>
                <span className="features-picker__mark" aria-hidden="true">
                  {on ? <Icon name="check" size={16} /> : null}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <p className="arrival__lead" role="note">
        {t(
          chosen.has("members")
            ? "account:arrival.import.choose.admin"
            : "account:arrival.import.choose.membersOff",
        )}
      </p>
    </fieldset>
  );
}
