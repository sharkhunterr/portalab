import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";

/**
 * Issue 355: the members' reviews of a title — its average and how many, mine to give (a rating from 1 to 5,
 * a few words if I want) once I watched, read, listened to or played it, and the others' (signed, or
 * « Anonymous » for a member who keeps to themselves).
 */
type ReviewsOut = components["schemas"]["ReviewsOut"];
type Review = components["schemas"]["ReviewOut"];

const KEY = (id: string) => ["media", "reviews", id] as const;

function useReviews(objectId: string) {
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
      {[1, 2, 3, 4, 5].map((n) => (
        <Icon key={n} name="star" size={14} className={n <= rating ? "is-on" : ""} />
      ))}
    </span>
  );
}

function StarPicker({ value, onChange }: { value: number; onChange: (rating: number) => void }) {
  const t = useT();
  const name = useId();
  return (
    <fieldset className="media-review__picker">
      <legend>{t("media:reviews.rating")}</legend>
      {[1, 2, 3, 4, 5].map((n) => (
        <label key={n} className={n <= value ? "is-on" : undefined}>
          <input
            type="radio"
            name={name}
            value={n}
            checked={value === n}
            onChange={() => onChange(n)}
            className="visually-hidden"
          />
          <Icon name="star" size={22} />
          <span className="visually-hidden">{t("media:reviews.stars", { count: n })}</span>
        </label>
      ))}
    </fieldset>
  );
}

function MyReview({ objectId, data }: { objectId: string; data: ReviewsOut }) {
  const t = useT();
  const client = useQueryClient();
  const commentId = useId();
  const mine = data.mine;
  const [editing, setEditing] = useState(!mine);
  const [rating, setRating] = useState(mine?.rating ?? 0);
  const [comment, setComment] = useState(mine?.comment ?? "");
  useEffect(() => {
    setRating(mine?.rating ?? 0);
    setComment(mine?.comment ?? "");
  }, [mine?.rating, mine?.comment]);
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
      setEditing(false);
    },
  });
  const remove = useMutation({
    mutationFn: async () =>
      api.DELETE("/api/v1/media/{object_id}/reviews/mine", { params: { path: { object_id: objectId } } }),
    onSuccess: () => {
      setEditing(true);
      void client.invalidateQueries({ queryKey: KEY(objectId) });
    },
  });
  if (!data.can_review && !mine) return <p className="media-review__hint">{t("media:reviews.notYet")}</p>;
  if (mine && !editing)
    return (
      <div className="media-review media-review--mine">
        <header>
          <strong>{t("media:reviews.mine")}</strong>
          <Stars rating={mine.rating} label={t("media:reviews.stars", { count: mine.rating })} />
        </header>
        {mine.comment ? <p>{mine.comment}</p> : null}
        <div className="media-review__actions">
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t("media:reviews.edit")}
          </Button>
          <Button variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {t("media:reviews.remove")}
          </Button>
        </div>
      </div>
    );
  return (
    <form
      className="media-review__form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        if (rating) save.mutate();
      }}
    >
      <StarPicker value={rating} onChange={setRating} />
      <div className="ds-field">
        <label htmlFor={commentId}>{t("media:reviews.comment")}</label>
        <textarea
          id={commentId}
          rows={3}
          maxLength={2000}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </div>
      <div className="media-review__actions">
        <Button type="submit" disabled={!rating || save.isPending}>
          {t(mine ? "media:reviews.update" : "media:reviews.submit")}
        </Button>
        {mine ? (
          <Button variant="ghost" onClick={() => setEditing(false)}>
            {t("media:reviews.cancel")}
          </Button>
        ) : null}
      </div>
      {save.isError ? <p role="alert">{t("media:reviews.error")}</p> : null}
    </form>
  );
}

function Line({ review }: { review: Review }) {
  const t = useT();
  const format = useFormat();
  return (
    <li className="media-review">
      <header>
        {review.author_id && review.author ? (
          <Link to={`/community/members/${review.author_id}`}>{review.author}</Link>
        ) : (
          <span className="media-review__anonymous">{t("media:reviews.anonymous")}</span>
        )}
        <Stars rating={review.rating} label={t("media:reviews.stars", { count: review.rating })} />
        <time dateTime={review.at}>{format.date(review.at)}</time>
      </header>
      {review.comment ? <p>{review.comment}</p> : null}
    </li>
  );
}

export function Reviews({ objectId }: { objectId: string }) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const reviews = useReviews(objectId);
  const data = reviews.data;
  if (!data?.reviewable) return null;
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
      <MyReview objectId={objectId} data={data} />
      {data.items.length ? (
        <ul className="media-reviews__list">
          {data.items.map((review) => (
            <Line key={`${review.author_id ?? "anonymous"}-${review.at}`} review={review} />
          ))}
        </ul>
      ) : data.mine ? null : (
        <p className="media-review__hint">{t("media:reviews.none")}</p>
      )}
    </section>
  );
}
