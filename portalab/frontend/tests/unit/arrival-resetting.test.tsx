import { describe, expect, it } from "vitest";
import { resetTasks } from "../../src/features/admin/arrival/Resetting";

// Issue 247 — the portal being reset shows every step the server tells: each data folder emptied, each
// module's data dropped, a new database, its permissions, Portalab's own packs written again.

const t = (id: string, values?: Record<string, string | number>) =>
  ({
    "account:reset.phase.files.visuals": "Erasing the visual packs",
    "account:reset.phase.files.other": `Erasing the folder “${values?.name}”`,
    "account:reset.phase.schema.drop": "Erasing the data, module by module",
  })[id] ?? id.slice("account:".length);

const run = {
  kind: "restore" as const,
  state: "running" as const,
  phase: "schema.drop",
  done: 3,
  total: 40,
  on: "identity",
  steps: ["files.visuals", "files.odd", "schema.drop", "schema.create", "schema.permissions", "schema.packs"],
  result: {},
  error: null,
};

describe("the portal's reset", () => {
  it("lists every step, the running one with what it is on", () => {
    const { tasks, percent } = resetTasks(run, false, false, t);
    expect(tasks.map((task) => [task.label, task.state])).toEqual([
      ["Erasing the visual packs", "done"],
      ["Erasing the folder “odd”", "done"],
      ["Erasing the data, module by module", "running"],
      ["reset.phase.schema.create", "waiting"],
      ["reset.phase.schema.permissions", "waiting"],
      ["reset.phase.schema.packs", "waiting"],
    ]);
    expect(tasks[2]?.detail).toBe("identity (4/40)");
    expect(percent).toBe(Math.round(((2 + 3 / 40) / 6) * 100));
  });

  it("over: every step done", () => {
    const { tasks, percent } = resetTasks({ ...run, state: "done", phase: "done" }, true, false, t);
    expect(tasks.every((task) => task.state === "done")).toBe(true);
    expect(percent).toBe(100);
  });
});
