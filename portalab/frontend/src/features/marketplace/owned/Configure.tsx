import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { type OwnershipRow, useOwnedActions } from "../api";
import { RequestForm } from "./Requests";

/** 027: a bought project launch — name the project, pitch it and say how much it needs (issue 304: a goal
 * the administrators confirm or change when they open its funding); it opens as a community proposal. */
function ProjectLaunchForm({ row }: { row: OwnershipRow }) {
  const t = useT();
  const { configure } = useOwnedActions();
  const [title, setTitle] = useState("");
  const [pitch, setPitch] = useState("");
  const [goal, setGoal] = useState("");
  return (
    <form
      className="ds-stack project-launch"
      onSubmit={(event) => {
        event.preventDefault();
        configure.mutate({ id: row.id, configuration: { title, pitch, goal: Number(goal) } });
      }}
    >
      <p className="ds-field__hint">{t("marketplace:owned.launchHint")}</p>
      <TextField
        label={t("marketplace:owned.launchTitle")}
        value={title}
        required
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className="ds-field">
        <label htmlFor={`pitch-${row.id}`}>{t("marketplace:owned.launchPitch")}</label>
        <textarea
          id={`pitch-${row.id}`}
          rows={4}
          maxLength={2000}
          value={pitch}
          onChange={(e) => setPitch(e.target.value)}
        />
      </div>
      <TextField
        type="number"
        min={1}
        label={t("marketplace:owned.launchGoal")}
        hint={t("marketplace:owned.launchGoalHint")}
        value={goal}
        required
        onChange={(e) => setGoal(e.target.value)}
      />
      <Button type="submit" disabled={!title.trim() || !(Number(goal) > 0) || configure.isPending}>
        {t("marketplace:owned.launch")}
      </Button>
    </form>
  );
}

export function NeedsConfiguration({ row }: { row: OwnershipRow }) {
  const t = useT();
  const { configure } = useOwnedActions();
  const [value, setValue] = useState("");
  if (row.product_type === "project_launch") return <ProjectLaunchForm row={row} />;
  if (row.product_type === "special_request") return <RequestForm row={row} />; // 027: a film in 4K…
  return (
    <form
      className="ds-stack--row"
      onSubmit={(event) => {
        event.preventDefault();
        configure.mutate({ id: row.id, configuration: { value } });
      }}
    >
      <TextField
        label={t("marketplace:owned.configureLabel")}
        value={value}
        required
        onChange={(e) => setValue(e.target.value)}
      />
      <Button type="submit">{t("marketplace:owned.configure")}</Button>
    </form>
  );
}
