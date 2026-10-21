import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { useRadio } from "./api";
import { RadioCard } from "./RadioCard";
import "./radio.css";

/** Issue 168: the radio's own page — listen, ask its DJ, what played. */
export default function RadioPage() {
  const t = useT();
  const radio = useRadio();
  return (
    <section className="radio-page" aria-labelledby="radio-title">
      <PageHeader
        titleId="radio-title"
        level={2}
        icon="radio"
        title={radio.data?.station ?? t("media:radio.title")}
        context={radio.data?.tagline ?? t("media:radio.lead")}
      />
      {radio.isPending ? (
        <FunctionalState state="loading" />
      ) : radio.isError || !radio.data?.available ? (
        <FunctionalState
          state="unavailable"
          label={t("media:radio.unavailable")}
          onRetry={() => radio.refetch()}
        />
      ) : (
        <div className="radio-page__card">
          <RadioCard radio={radio.data} history />
        </div>
      )}
    </section>
  );
}
