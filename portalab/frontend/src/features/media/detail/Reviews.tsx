import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";

/**
 * Issue 355: the members' reviews of a title. Mine is given in a dialog opened from the title's head (« Give
 * my review », or my rating once given): five stars that say what they mean, a few words if I want. The
 * page lists the reviews below — the average, how many, each signed or « Anonymous » — only when there are.
 */
type ReviewsOut = components["schemas"]["ReviewsOut"];
type Review = components["schemas"]["ReviewOut"];

const KEY = (id: string) => ["media", "reviews", id] as const;
const RATINGS = [1, 2, 3, 4, 5] as const;

export function useReviews(objectId: string) {
  return useQuery({
    queryKey: KEY(objectId),
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/media/{object_id}/reviews", { params: { path: { object_id: objectId } } }))
        .data ?? null,
  });
}

function Stars({ rating, label }: { rating: number; label: string }) {
  return (
    <span className="media-review__stars" role="img" aria-label={label}>
      {RATINGS.map((n) => (
        <Icon key={n} name="star" size={14} className={n <= rating ? "is-on" : ""} />
      ))}
    </span>
  );
}

function StarPicker({ value, onChange }: { value: number; onChange: (rating: number) => void }) {
  const t = useT();
  const name = useId();
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <fieldset className="media-review__picker" onMouseLeave={() => setHover(0)}>
      <legend>{t("media:reviews.rating")}</legend>
      <div className="media-review__picker-stars">
        {RATINGS.map((n) => (
          <label key={n} className={n <= shown ? "is-on" : undefined} onMouseEnter={() => setHover(n)}>
            <input
              type="radio"
              name={name}
              value={n}
              checked={value === n}
              onChange={() => onChange(n)}
              className="visually-hidden"
            />
            <Icon name="star" size={34} />
            <span className="visually-hidden">
              {t("media:reviews.stars", { count: n })} — {t(`media:reviews.meaning.${n}`)}
            </span>
          </label>
        ))}
      </div>
      <p className="media-review__meaning" aria-hidden="true">
        {shown ? t(`media:reviews.meaning.${shown}`) : t("media:reviews.pick")}
      </p>
    </fieldset>
  );
}

/** My review in a dialog: give it, change it or take it back. */
interface Shown {
  objectId: string;
  title: string;
  /** the title's poster and facts, at the head of the dialog (issue 354) */
  poster?: string | null | undefined;
  facts?: string | undefined;
}

export function ReviewDialog({
  objectId,
  title,
  poster,
  facts,
  data,
  open,
  onOpenChange,
}: Shown & {
  data: ReviewsOut;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useT();
  const client = useQueryClient();
  const formId = useId();
  const mine = data.mine;
  const [rating, setRating] = useState(mine?.rating ?? 0);
  const [comment, setComment] = useState(mine?.comment ?? "");
  useEffect(() => {
    if (open) {
      setRating(mine?.rating ?? 0);
      setComment(mine?.comment ?? "");
    }
  }, [open, mine?.rating, mine?.comment]);
  const save = useMutation({
    mutationFn: async () =>
      (
        await api.PUT("/api/v1/media/{object_id}/reviews/mine", {
          params: { path: { object_id: objectId } },
          body: { rating, comment: comment.trim() || null },
        })
      ).data,
    onSuccess: (next) => {
      if (next) client.setQueryData(KEY(objectId), next);
      onOpenChange(false);
    },
  });
  const remove = useMutation({
    mutationFn: async () =>
      api.DELETE("/api/v1/media/{object_id}/reviews/mine", { params: { path: { object_id: objectId } } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY(objectId) });
      onOpenChange(false);
    },
  });
  return (
    <Dialog
      trigger={null}
      open={open}
      onOpenChange={onOpenChange}
      title={t("media:reviews.dialogTitle")}
      closeLabel={t("media:reviews.cancel")}
      footer={
        <>
          {mine ? (
            <Button variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
              {t("media:reviews.remove")}
            </Button>
          ) : null}
          <Button type="submit" form={formId} disabled={!rating || save.isPending}>
            {t(mine ? "media:reviews.update" : "media:reviews.submit")}
          </Button>
        </>
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
      <form
        id={formId}
        className="media-review__form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (rating) save.mutate();
        }}
      >
        <StarPicker value={rating} onChange={setRating} />
        <div className="ds-field">
          <label htmlFor={`${formId}-comment`}>{t("media:reviews.comment")}</label>
          <textarea
            id={`${formId}-comment`}
            rows={4}
            maxLength={2000}
            placeholder={t("media:reviews.commentHint")}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
        {save.isError ? <p role="alert">{t("media:reviews.error")}</p> : null}
      </form>
    </Dialog>
  );
}

/** Issue 355: in the title's head — « Give my review » once seen, read or played; my rating once given. */
export function ReviewButton({ objectId, title, poster, facts }: Shown) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const data = useReviews(objectId).data;
  if (!data?.reviewable || (!data.can_review && !data.mine)) return null;
  const mine = data.mine;
  return (
    <>
      <button
        type="button"
        className="media-action"
        data-on={mine ? true : undefined}
        onClick={() => setOpen(true)}
        title={mine ? t("media:reviews.edit") : t("media:reviews.give")}
      >
        <Icon name="star" size={16} />
        <span>{mine ? t("media:reviews.myRating", { rating: mine.rating }) : t("media:reviews.give")}</span>
      </button>
      <ReviewDialog
        objectId={objectId}
        title={title}
        poster={poster}
        facts={facts}
        data={data}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}

function Line({ review, onEdit }: { review: Review; onEdit?: () => void }) {
  const t = useT();
  const format = useFormat();
  return (
    <li className="media-review" data-mine={review.mine || undefined}>
      <header>
        {review.mine ? (
          <strong>{t("media:reviews.mine")}</strong>
        ) : review.author_id && review.author ? (
          <Link to={`/community/members/${review.author_id}`}>{review.author}</Link>
        ) : (
          <span className="media-review__anonymous">{t("media:reviews.anonymous")}</span>
        )}
        <Stars rating={review.rating} label={t("media:reviews.stars", { count: review.rating })} />
        <time dateTime={review.at}>{format.date(review.at)}</time>
        {onEdit ? (
          <button type="button" className="media-review__edit" onClick={onEdit}>
            {t("media:reviews.edit")}
          </button>
        ) : null}
      </header>
      {review.comment ? <p>{review.comment}</p> : null}
    </li>
  );
}

export function Reviews({ objectId, title, poster, facts }: Shown) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const [open, setOpen] = useState(false);
  const data = useReviews(objectId).data;
  if (!data?.reviewable || !data.count) return null;
  return (
    <section aria-labelledby={headingId} className="media-section media-reviews">
      <h3 id={headingId}>
        <Icon name="star" size={18} />
        {t("media:reviews.title")}
        {data.average !== null && data.average !== undefined ? (
          <span className="media-reviews__average">
            {t("media:reviews.average", {
              average: format.number(Math.round(data.average * 10) / 10),
              count: data.count,
            })}
          </span>
        ) : null}
      </h3>
      <ul className="media-reviews__list">
        {data.mine ? <Line review={data.mine} onEdit={() => setOpen(true)} /> : null}
        {data.items.map((review) => (
          <Line key={`${review.author_id ?? "anonymous"}-${review.at}`} review={review} />
        ))}
      </ul>
      {data.mine ? (
        <ReviewDialog
          objectId={objectId}
          title={title}
          poster={poster}
          facts={facts}
          data={data}
          open={open}
          onOpenChange={setOpen}
        />
      ) : null}
    </section>
  );
}
