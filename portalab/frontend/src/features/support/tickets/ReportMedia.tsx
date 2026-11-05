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
 * ticket of the type the administrator chose for it (its own fields: what is wrong), about this media: the
 * team sees the media in the ticket and opens it in a click. No such type, or no tickets: no button.
 */
export function ReportMediaProblem({ objectId, title }: { objectId: string; title: string }) {
  const t = useT();
  const formId = useId();
  const client = useQueryClient();
  const types = useTicketTypes();
  const { create } = useTicketActions("");
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState("");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [created, setCreated] = useState<string | null>(null);
  const type = Array.isArray(types.data) ? types.data.find((x) => x.media) : undefined;
  if (!type) return null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        type_key: type.key,
        title: t("support:media.ticketTitle", { title }).slice(0, 200),
        description: problem,
        fields: values,
        priority: "normal",
        media_id: objectId,
      },
      {
        onSuccess: (ticket) => {
          setCreated(ticket.id);
          setProblem("");
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
      title={t("support:media.title", { title })}
      closeLabel={t("support:media.close")}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setCreated(null);
      }}
      footer={
        created ? null : (
          <Button type="submit" form={formId} disabled={create.isPending}>
            {t("support:media.submit")}
          </Button>
        )
      }
      trigger={
        <button type="button" className="media-report" title={t("support:media.hint")}>
          <Icon name="flag" size={16} />
          <span>{t("support:media.report")}</span>
        </button>
      }
    >
      {created ? (
        <p className="media-report__done" role="status">
          <Icon name="check" size={16} />
          {t("support:media.done")} <Link to={`/support/tickets/${created}`}>{t("support:media.see")}</Link>
        </p>
      ) : (
        <form id={formId} onSubmit={submit} className="media-report__form">
          <p className="media-report__lead">{t("support:media.lead")}</p>
          <FieldInputs
            defs={type.fields as unknown as FieldDef[]}
            values={values}
            onChange={setValues}
            errors={missing}
          />
          <div className="ds-field">
            <label htmlFor={`${formId}-problem`}>{t("support:media.problem")}</label>
            <textarea
              id={`${formId}-problem`}
              rows={4}
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
