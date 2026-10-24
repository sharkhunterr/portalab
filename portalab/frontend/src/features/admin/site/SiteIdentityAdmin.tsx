import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useMemo, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminGrid, AdminPage, AdminSection, FormActions } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { ICONS, Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { SITE_KEY } from "../../../shell/site/site";
import { ApiError } from "../../../state/regions";
import "../admin.css";
import "./site.css";

type SiteAdmin = components["schemas"]["SiteAdminOut"];
type Names = { one: string; other: string };
type Image = "logo" | "icon";
const ADMIN_KEY = ["admin", "site"] as const;
// the currency's icons on offer (any icon of the portal would do; these read as a currency)
const CURRENCY_ICONS = [
  "coins",
  "gem",
  "diamond",
  "hexagon",
  "star",
  "sparkle",
  "crown",
  "medal",
  "award",
  "flame",
  "zap",
  "atom",
  "orbit",
  "rocket",
  "potion",
  "leaf",
  "cookie",
  "candy",
  "skull",
  "ghost",
].filter((name) => ICONS[name]);

interface Form {
  name: string;
  short_name: string;
  tagline: Record<string, string>;
  currency: Record<string, Names>;
  currency_short: string;
  currency_icon: string;
}

function formOf(site: SiteAdmin | undefined): Form {
  return {
    name: site?.name ?? "",
    short_name: site?.short_name ?? "",
    tagline: { ...(site?.tagline ?? {}) },
    currency: Object.fromEntries(
      Object.entries(site?.currency ?? {}).map(([language, names]) => [
        language,
        { one: names.one ?? "", other: names.other ?? "" },
      ]),
    ),
    currency_short: site?.currency_short ?? "",
    currency_icon: site?.currency_icon ?? "",
  };
}

function useLanguages() {
  return useQuery({
    queryKey: ["i18n", "languages"],
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/i18n/languages")).data as unknown as {
        default: string;
        items: Array<{ code: string; name_native: string }>;
      },
  });
}

/** A chosen image, before it is sent: its preview in this page only. */
function usePreview(file: File | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return url;
}

function ImageField({
  which,
  current,
  file,
  removed,
  onFile,
  onRemove,
}: {
  which: Image;
  current: string | null;
  file: File | null;
  removed: boolean;
  onFile: (file: File | null) => void;
  onRemove: () => void;
}) {
  const t = useT();
  const id = useId();
  const preview = usePreview(file);
  const shown = preview ?? (removed ? null : current);
  return (
    <div className="site-image" data-which={which}>
      <div className="site-image__frame">
        {shown ? (
          <img src={shown} alt={t(`admin:site.${which}.alt`)} />
        ) : (
          <span className="admin-muted">{t("admin:site.image.none")}</span>
        )}
      </div>
      <div className="site-image__controls">
        <label className="ds-button ds-button--secondary" htmlFor={id}>
          <Icon name="camera" size={16} />
          {t("admin:site.image.choose")}
        </label>
        <input
          id={id}
          className="visually-hidden"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={(event) => onFile(event.target.files?.[0] ?? null)}
        />
        {shown ? (
          <Button variant="ghost" onClick={onRemove}>
            <Icon name="trash" size={16} />
            {t("admin:site.image.remove")}
          </Button>
        ) : null}
      </div>
      <p className="admin-muted">{t(`admin:site.${which}.hint`)}</p>
    </div>
  );
}

/** What members will see: the header, the sign-in card, a price — before anything is saved. */
function Preview({
  form,
  logo,
  language,
  defaultName,
}: {
  form: Form;
  logo: string | null;
  language: string;
  defaultName: string;
}) {
  const t = useT();
  const name = form.name.trim() || defaultName;
  const names = form.currency[language] ?? Object.values(form.currency)[0];
  const one = names?.one.trim() || names?.other.trim() || t("gamification:value.coins");
  const other = names?.other.trim() || one;
  const rules = useMemo(() => new Intl.PluralRules(language), [language]);
  const word = (amount: number) => (rules.select(amount) === "one" ? one : other);
  const tagline = form.tagline[language]?.trim() || Object.values(form.tagline).find((v) => v.trim());
  return (
    <div className="site-preview">
      <div className="site-preview__header">
        {logo ? (
          <img className="shell-brand__logo" src={logo} alt="" />
        ) : (
          <span className="shell-brand__mark" aria-hidden="true">
            <Icon name="sparkles" size={18} />
          </span>
        )}
        <strong>{name}</strong>
        <span className="site-preview__phone" title={t("admin:site.preview.phone")}>
          <Icon name="smartphone" size={14} /> {form.short_name.trim() || name.slice(0, 12)}
        </span>
      </div>
      <div className="site-preview__card">
        <strong>{name}</strong>
        <p>{tagline ?? t("admin:site.preview.defaultTagline")}</p>
      </div>
      <ul className="site-preview__lines">
        <li>{t("admin:site.preview.spend", { amount: "1", currency: word(1) })}</li>
        <li>{t("admin:site.preview.spend", { amount: "120", currency: word(120) })}</li>
        <li>{t("admin:site.preview.balance", { currency: other })}</li>
        <li>
          <span className="ds-coins">
            <Icon name={form.currency_icon || "coins"} size={18} />
            <span>
              120
              {form.currency_short.trim() ? (
                <span className="ds-currency-short">{` ${form.currency_short.trim()}`}</span>
              ) : null}
            </span>
          </span>
        </li>
      </ul>
    </div>
  );
}

/**
 * Issue 159 — Administration › System › Site identity: the site's name (instead of « Portalab ») and short
 * name, its slogan per language, its logo and icon (the tab, the home screen), its currency (instead of
 * « Coins ») in the singular and the plural per language, a short name and an icon. A preview shows the
 * result before saving; « Restore Portalab's » empties it all. The administration's technical texts keep
 * the software's name.
 */
export function SiteIdentityAdmin({ embedded = false }: { embedded?: boolean } = {}) {
  const t = useT();
  const client = useQueryClient();
  const current = useQuery({
    queryKey: ADMIN_KEY,
    queryFn: async () => (await api.GET("/api/v1/admin/site")).data as SiteAdmin,
  });
  const languages = useLanguages();
  const codes = useMemo(() => {
    const listed = (languages.data?.items ?? []).map((item) => item.code);
    return listed.length ? listed : ["en", "fr"];
  }, [languages.data]);
  const [form, setForm] = useState<Form>(formOf(undefined));
  const [files, setFiles] = useState<Record<Image, File | null>>({ logo: null, icon: null });
  const [removed, setRemoved] = useState<Record<Image, boolean>>({ logo: false, icon: false });
  const [previewLanguage, setPreviewLanguage] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [saved, setSaved] = useState(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: start again from what the server holds
  useEffect(() => {
    if (current.data) {
      setForm(formOf(current.data));
      setFiles({ logo: null, icon: null });
      setRemoved({ logo: false, icon: false });
    }
  }, [current.data?.version]);
  const language = previewLanguage || languages.data?.default || codes[0] || "en";
  const logoFile = usePreview(files.logo);
  const logo = logoFile ?? (removed.logo ? null : (current.data?.logo ?? null));

  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ADMIN_KEY });
    await client.invalidateQueries({ queryKey: SITE_KEY });
    await client.invalidateQueries({ queryKey: ["i18n", "catalog"] }); // the site's words in the messages
  };
  const save = useMutation({
    mutationFn: async () => {
      await api.PUT("/api/v1/admin/site", {
        body: {
          name: form.name.trim() || null,
          short_name: form.short_name.trim() || null,
          tagline: form.tagline,
          currency: form.currency,
          currency_short: form.currency_short.trim() || null,
          currency_icon: form.currency_icon || null,
        },
      });
      for (const which of ["logo", "icon"] as const) {
        const file = files[which];
        if (file) {
          await api.PUT("/api/v1/admin/site/{which}", {
            params: { path: { which } },
            body: file as unknown as string,
            bodySerializer: (body) => body as unknown as BodyInit,
            headers: { "Content-Type": file.type || "application/octet-stream" },
          });
        } else if (removed[which]) {
          await api.DELETE("/api/v1/admin/site/{which}", { params: { path: { which } } });
        }
      }
    },
    onSuccess: async () => {
      setSaved(true);
      await refresh();
    },
    onError: () => setSaved(false),
  });
  const reset = useMutation({
    mutationFn: async () => api.DELETE("/api/v1/admin/site"),
    onSuccess: async () => {
      setConfirmReset(false);
      await refresh();
    },
  });

  const change = (patch: Partial<Form>) => {
    setSaved(false);
    setForm((previous) => ({ ...previous, ...patch }));
  };
  const names = (code: string): Names => form.currency[code] ?? { one: "", other: "" };
  const setNames = (code: string, patch: Partial<Names>) =>
    change({ currency: { ...form.currency, [code]: { ...names(code), ...patch } } });
  const nameOf = (code: string) =>
    languages.data?.items.find((item) => item.code === code)?.name_native ?? code;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const defaultName = current.data?.default_name ?? "Portalab";
  const error = save.error ?? reset.error;

  // issue 6: the same form inside the setup assistant's first step
  const content = (
    <form className="site-admin" onSubmit={submit}>
      <AdminGrid>
        <AdminSection icon="sparkles" title={t("admin:site.name.title")}>
          <TextField
            label={t("admin:site.name.label")}
            hint={t("admin:site.name.hint", { name: defaultName })}
            placeholder={defaultName}
            maxLength={40}
            value={form.name}
            onChange={(event) => change({ name: event.target.value })}
          />
          <TextField
            label={t("admin:site.shortName.label")}
            hint={t("admin:site.shortName.hint")}
            maxLength={12}
            value={form.short_name}
            onChange={(event) => change({ short_name: event.target.value })}
          />
          {codes.map((code) => (
            <TextField
              key={code}
              label={t("admin:site.tagline.label", { language: nameOf(code) })}
              hint={code === codes[0] ? t("admin:site.tagline.hint") : undefined}
              maxLength={160}
              value={form.tagline[code] ?? ""}
              onChange={(event) => change({ tagline: { ...form.tagline, [code]: event.target.value } })}
            />
          ))}
        </AdminSection>

        <AdminSection icon="camera" title={t("admin:site.images.title")}>
          {(["logo", "icon"] as const).map((which) => (
            <div key={which}>
              <h4 className="site-admin__subtitle">{t(`admin:site.${which}.title`)}</h4>
              <ImageField
                which={which}
                current={current.data?.[which] ?? null}
                file={files[which]}
                removed={removed[which]}
                onFile={(file) => {
                  setSaved(false);
                  setFiles((previous) => ({ ...previous, [which]: file }));
                  setRemoved((previous) => ({ ...previous, [which]: false }));
                }}
                onRemove={() => {
                  setSaved(false);
                  setFiles((previous) => ({ ...previous, [which]: null }));
                  setRemoved((previous) => ({ ...previous, [which]: true }));
                }}
              />
            </div>
          ))}
        </AdminSection>

        <AdminSection
          icon="coins"
          title={t("admin:site.currency.title")}
          description={t("admin:site.currency.description")}
        >
          {codes.map((code) => (
            <fieldset key={code} className="site-admin__currency">
              <legend>{nameOf(code)}</legend>
              <TextField
                label={t("admin:site.currency.one")}
                placeholder="Coin"
                maxLength={30}
                value={names(code).one}
                onChange={(event) => setNames(code, { one: event.target.value })}
              />
              <TextField
                label={t("admin:site.currency.other")}
                placeholder="Coins"
                maxLength={30}
                value={names(code).other}
                onChange={(event) => setNames(code, { other: event.target.value })}
              />
            </fieldset>
          ))}
          <TextField
            label={t("admin:site.currency.short")}
            hint={t("admin:site.currency.shortHint")}
            maxLength={8}
            value={form.currency_short}
            onChange={(event) => change({ currency_short: event.target.value })}
          />
          <SelectField
            label={t("admin:site.currency.icon")}
            hint={t("admin:site.currency.iconHint")}
            value={form.currency_icon}
            onChange={(event) => change({ currency_icon: event.target.value })}
          >
            <option value="">{t("admin:site.currency.iconDefault")}</option>
            {CURRENCY_ICONS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </SelectField>
        </AdminSection>

        <AdminSection
          icon="eye"
          title={t("admin:site.preview.title")}
          description={t("admin:site.preview.description")}
          actions={
            codes.length > 1 ? (
              <SelectField
                label={t("admin:site.preview.language")}
                value={language}
                onChange={(event) => setPreviewLanguage(event.target.value)}
              >
                {codes.map((code) => (
                  <option key={code} value={code}>
                    {nameOf(code)}
                  </option>
                ))}
              </SelectField>
            ) : null
          }
        >
          <Preview form={form} logo={logo} language={language} defaultName={defaultName} />
        </AdminSection>
      </AdminGrid>

      {error ? (
        <p className="ds-field__error" role="alert">
          {error instanceof ApiError ? error.message : t("admin:site.failed")}
        </p>
      ) : null}
      {saved && !save.isPending ? (
        <p className="admin-muted" role="status">
          <Icon name="check" size={14} /> {t("admin:site.saved")}
        </p>
      ) : null}
      <FormActions>
        <Dialog
          open={confirmReset}
          onOpenChange={setConfirmReset}
          title={t("admin:site.reset")}
          closeLabel={t("admin:site.cancel")}
          trigger={
            <Button variant="secondary" disabled={!current.data?.custom && !current.data?.version}>
              <Icon name="sync" size={16} />
              {t("admin:site.reset")}
            </Button>
          }
          footer={
            <Button onClick={() => reset.mutate()} disabled={reset.isPending}>
              {t("admin:site.reset")}
            </Button>
          }
        >
          <p>{t("admin:site.resetConfirm", { name: defaultName })}</p>
        </Dialog>
        <Button type="submit" disabled={save.isPending || !current.data}>
          <Icon name="check" size={16} />
          {t("admin:site.save")}
        </Button>
      </FormActions>
    </form>
  );
  return embedded ? (
    content
  ) : (
    <AdminPage icon="sparkles" title={t("admin:site.title")} description={t("admin:site.description")}>
      {content}
    </AdminPage>
  );
}
