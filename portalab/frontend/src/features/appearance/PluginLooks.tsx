import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { productTypeLabel } from "../marketplace/typeLabel";
import { InShop } from "./InShop";
import { RarityTag, rarityIn } from "./Rarity";

export interface PluginLook {
  key: string;
  locked: boolean;
  rarity?: string | null;
  names?: Record<string, string>;
}

export interface PluginKind {
  type: string;
  plugin: string;
  plugin_name?: string;
  label_key: string;
  icon?: string | null;
  looks: PluginLook[];
}

/**
 * 030: each kind of visual an extension adds (its message bubbles…) is a block of Appearance of its own,
 * like Portalab's — named by the extension; « plain » and the looks the member owns, how many more the shop
 * sells in one line. The extension wears the choice.
 */
export function PluginLooks() {
  const catalog = useQuery({
    queryKey: ["ui", "plugin-looks"],
    retry: false,
    queryFn: async () => ((await api.GET("/api/v1/ui/plugin-looks")).data ?? []) as unknown as PluginKind[],
  });
  const kinds = Array.isArray(catalog.data) ? catalog.data : [];
  return (
    <>
      {kinds.map((kind) => (
        <PluginKindLooks key={kind.type} kind={kind} />
      ))}
    </>
  );
}

function PluginKindLooks({ kind }: { kind: PluginKind }) {
  const t = useT();
  const { language } = useLocaleContext();
  const { preferences, setPreference } = usePreferences();
  const owned = kind.looks.filter((look) => !look.locked);
  const current = preferences.pluginLooks[kind.type] ?? null;
  const id = `plugin-looks-${kind.type.replace(/[^a-z0-9]/g, "-")}`;
  const choose = (look: string | null) => {
    const next = { ...preferences.pluginLooks };
    if (look) next[kind.type] = look;
    else delete next[kind.type];
    setPreference("pluginLooks", next);
  };
  const nameOf = (look: PluginLook) => look.names?.[language] ?? look.names?.en ?? look.key;
  return (
    <section className="looks appearance-card" aria-labelledby={id} data-kind={kind.type}>
      <h3 id={id}>{productTypeLabel(t, kind.type)}</h3>
      <p className="ds-page-header__context">
        {t("notifications:pluginLooks.hint", { plugin: kind.plugin_name ?? kind.plugin })}
      </p>
      <fieldset className="looks__animations">
        <legend className="visually-hidden">{productTypeLabel(t, kind.type)}</legend>
        {[null, ...owned].map((look) => {
          const key = look?.key ?? null;
          return (
            <label
              key={key ?? ""}
              className="looks__chip"
              data-current={current === key || undefined}
              data-rarity={key ? rarityIn(kind.looks, key) : undefined}
            >
              <input
                type="radio"
                name={id}
                value={key ?? ""}
                checked={current === key}
                onChange={() => choose(key)}
              />
              <Icon name={kind.icon ?? "sparkles"} size={14} />
              {look ? nameOf(look) : t("notifications:pluginLooks.none")}
              {key ? <RarityTag rarity={rarityIn(kind.looks, key)} /> : null}
            </label>
          );
        })}
      </fieldset>
      <InShop count={kind.looks.length - owned.length} type={kind.type} />
    </section>
  );
}
