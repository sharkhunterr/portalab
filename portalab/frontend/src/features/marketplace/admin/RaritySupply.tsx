import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { RARITIES } from "./ProductEditor";

/**
 * Rarities and copies (027): how many copies of a product of each rarity may exist — common products are
 * usually unlimited, a legendary one a couple. A product may set its own number (availability dialog).
 */
export function RaritySupply() {
  const t = useT();
  const client = useQueryClient();
  const rarities = useQuery({
    queryKey: ["marketplace", "admin", "rarities"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/marketplace/rarities")).data ?? {}) as Record<string, number | null>,
  });
  const [values, setValues] = useState<Record<string, string>>({});
  const [state, setState] = useState<"idle" | "saved" | "error">("idle");
  useEffect(() => {
    if (rarities.data) {
      setValues(Object.fromEntries(RARITIES.map((r) => [r, String(rarities.data[r] ?? "")])));
    }
  }, [rarities.data]);
  const save = async () => {
    setState("idle");
    try {
      await api.PUT("/api/v1/admin/marketplace/rarities", {
        body: {
          supply: Object.fromEntries(
            RARITIES.map((r) => [r, values[r]?.trim() ? Math.max(1, Number(values[r])) : null]),
          ),
        },
      });
      setState("saved");
      void client.invalidateQueries({ queryKey: ["marketplace"] });
    } catch {
      setState("error");
    }
  };
  return (
    <AdminSection
      title={t("marketplace:admin.rarities")}
      description={t("marketplace:admin.raritiesHint")}
      icon="star"
      actions={<Button onClick={save}>{t("marketplace:admin.save")}</Button>}
    >
      <div className="rarity-supply">
        {RARITIES.map((rarity) => (
          <div key={rarity} className="rarity-supply__item" data-rarity={rarity}>
            <TextField
              label={t(`marketplace:rarity.${rarity}`)}
              type="number"
              min={1}
              max={1000000}
              placeholder={t("marketplace:admin.unlimited")}
              value={values[rarity] ?? ""}
              onChange={(e) => setValues({ ...values, [rarity]: e.target.value })}
            />
          </div>
        ))}
      </div>
      {state === "saved" ? <p role="status">{t("marketplace:admin.done")}</p> : null}
      {state === "error" ? <p role="alert">{t("marketplace:admin.error")}</p> : null}
    </AdminSection>
  );
}
