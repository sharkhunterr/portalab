import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";

const STORED = "portalab.newsletters.livePreview";

/** issue 327: the live preview writes an edition at each change — on demand, off by default, remembered. */
export function useLivePreview(): [boolean, (on: boolean) => void] {
  const [live, setLive] = useState(() => {
    try {
      return window.localStorage.getItem(STORED) === "1";
    } catch {
      return false;
    }
  });
  return [
    live,
    (on: boolean) => {
      setLive(on);
      try {
        window.localStorage.setItem(STORED, on ? "1" : "0");
      } catch {
        // a private window keeps no choice: it lasts for the page
      }
    },
  ];
}

/** The preview's head: live or not, and « preview now » while it is not. */
export function PreviewSwitch({
  live,
  onLive,
  onPreview,
  busy,
}: {
  live: boolean;
  onLive: (on: boolean) => void;
  onPreview: () => void;
  busy: boolean;
}) {
  const t = useT();
  return (
    <div className="edition-preview-head">
      <label className="edition-content" data-checked={live || undefined}>
        <input type="checkbox" checked={live} onChange={(e) => onLive(e.target.checked)} />
        <Icon name="eye" size={14} />
        {t("news:preview.live")}
      </label>
      {live ? null : (
        <Button variant="secondary" disabled={busy} onClick={onPreview}>
          <Icon name="sync" size={16} />
          {t("news:preview.now")}
        </Button>
      )}
    </div>
  );
}
