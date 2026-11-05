import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { useMediaDetail } from "../../media/api";
import { type FieldDef, useTicketActions, useTicketTypes } from "./api";
import { FieldInputs } from "./FieldInputs";
import "../support.css";

/**
 * Issue 354: « Report a problem » on a media's page — subtitles missing, the wrong language, a cut file… A
 * ticket of the type that takes media reports, about this media (its poster heads the dialog): the team sees
 * the media in the ticket and opens it in a click. What is wrong is picked first among the type's own kinds
 * of problem (its ``problem`` choice, set by the administrators), else the portal's own; it heads the
 * ticket's title. No such type, or no tickets: no button.
 */
export const PROBLEM_FIELD = "problem";
export const DEFAULT_PROBLEMS = ["subtitles", "sound", "image", "language", "file", "other"] as const;
const DEFAULT_ICONS: Record<string, string> = {
  subtitles: "captions",
  sound: "volume",
  image: "image",
  language: "globe",
  file: "blocked",
  other: "more",
};

/** An icon for a kind of problem the administrators named, from its words. */
export function problemIcon(label: string): string {
  const words = label.toLocaleLowerCase();
  if (/sous-titr|subtit|caption/.test(words)) return "captions";
  if (/\bson\b|sound|audio|volume|bruit/.test(words)) return "volume";
  if (/image|picture|vid[ée]o|qualit|pixel/.test(words)) return "image";
  if (/langu|vf|vo\b|doubl/.test(words)) return "globe";
  if (/fichier|file|coup|lecture|play|illisible/.test(words)) return "blocked";
  return "flag";
}

/** The kinds of problem a media report offers: the type's own (``problem`` choice), else the portal's. */
export function useProblems(
  fields: FieldDef[] | undefined,
): Array<{ value: string; label: string; icon: string }> {
  const t = useT();
  const own = fields?.find((f) => f.key === PROBLEM_FIELD && f.type === "select");
  const options = (own?.options ?? []).filter((o): o is string => typeof o === "string" && o.trim() !== "");
  if (options.length) return options.map((o) => ({ value: o, label: o, icon: problemIcon(o) }));
  return DEFAULT_PROBLEMS.map((key) => ({
    value: key,
    label: t(`support:media.kind.${key}`),
    icon: DEFAULT_ICONS[key] ?? "flag",
  }));
}

export function ReportMediaProblem({
  objectId,
  title,
  poster,
  facts,
}: {
  objectId: string;
  title: string;
  poster?: string | null;
  /** what the dialog says under the title: « 2026 · Film » */
  facts?: string;
}) {
  const t = useT();
  const formId = useId();
  const client = useQueryClient();
  const types = useTicketTypes();
  const { create } = useTicketActions("");
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState("");
  const [kind, setKind] = useState<string>("");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [created, setCreated] = useState<string | null>(null);
  const type = Array.isArray(types.data) ? types.data.find((x) => x.media) : undefined;
  const defs = (type?.fields ?? []) as unknown as FieldDef[];
  const problems = useProblems(defs);
  if (!type) return null;
  const own = defs.some((f) => f.key === PROBLEM_FIELD && f.type === "select");
  const others = defs.filter((f) => f.key !== PROBLEM_FIELD);
  const chosen = problems.find((p) => p.value === kind);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!chosen) return;
    create.mutate(
      {
        type_key: type.key,
        title: t("support:media.ticketTitle", { problem: chosen.label, title }).slice(0, 200),
        description: problem,
        fields: own ? { ...values, [PROBLEM_FIELD]: chosen.value } : values,
        priority: "normal",
        media_id: objectId,
      },
      {
        onSuccess: (ticket) => {
          setCreated(ticket.id);
          setProblem("");
          setKind("");
          setValues({});
          void client.invalidateQueries({ queryKey: ["support", "mine"] });
        },
      },
    );
  };
  const missing =
    create.error instanceof ApiError ? ((create.error.extensions.fields as string[] | undefined) ?? []) : [];
  return (
    <Dialog
      title={t("support:media.title")}
      closeLabel={t("support:media.close")}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setCreated(null);
      }}
      footer={
        created ? null : (
          <Button type="submit" form={formId} disabled={!kind || create.isPending}>
            {t("support:media.submit")}
          </Button>
        )
      }
      trigger={
        <button
          type="button"
          className="media-action media-action--icon media-action--warn"
          title={t("support:media.report")}
          aria-label={t("support:media.report")}
        >
          <Icon name="flag" size={16} />
        </button>
      }
    >
      <div className="media-dialog__head">
        {poster ? (
          <img className="media-dialog__poster" src={poster} alt="" />
        ) : (
          <span className="media-dialog__poster media-dialog__poster--none" aria-hidden="true">
            <Icon name="film" size={28} />
          </span>
        )}
        <div className="media-dialog__title">
          <strong>{title}</strong>
          {facts ? <span>{facts}</span> : null}
        </div>
      </div>
      {created ? (
        <p className="media-report__done" role="status">
          <Icon name="check" size={16} />
          {t("support:media.done")} <Link to={`/support/tickets/${created}`}>{t("support:media.see")}</Link>
        </p>
      ) : (
        <form id={formId} onSubmit={submit} className="media-report__form">
          <fieldset className="media-report__kinds">
            <legend>{t("support:media.what")}</legend>
            {problems.map((item) => (
              <label key={item.value} data-on={kind === item.value || undefined}>
                <input
                  type="radio"
                  name={`${formId}-kind`}
                  value={item.value}
                  checked={kind === item.value}
                  onChange={() => setKind(item.value)}
                  className="visually-hidden"
                />
                <Icon name={item.icon} size={18} />
                <span>{item.label}</span>
              </label>
            ))}
          </fieldset>
          <FieldInputs defs={others} values={values} onChange={setValues} errors={missing} />
          <div className="ds-field">
            <label htmlFor={`${formId}-problem`}>{t("support:media.problem")}</label>
            <textarea
              id={`${formId}-problem`}
              rows={3}
              placeholder={t("support:media.lead")}
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
            />
          </div>
          {create.isError ? (
            <p role="alert">
              {missing.length
                ? t("support:new.missing", { fields: missing.join(", ") })
                : t("support:new.failed")}
            </p>
          ) : null}
        </form>
      )}
    </Dialog>
  );
}

/** Issue 354: the media a ticket is about, on the ticket — its title, a link to its page. */
export function TicketMedia({ objectId }: { objectId: string }) {
  const t = useT();
  const media = useMediaDetail(objectId);
  return (
    <Link to={`/media/${objectId}`} className="ticket-media">
      <Icon name="film" size={14} />
      <span>
        {media.data
          ? t("support:media.about", { title: media.data.title, kind: t(`media:kind.${media.data.kind}`) })
          : t("support:media.aboutUnknown")}
      </span>
      <Icon name="chevron-right" size={14} />
    </Link>
  );
}
