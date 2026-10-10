import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import "../../src/features/services/HostWidgets";
import { widgetComponent } from "../../src/features/dashboard/widgets/registry";

// #49/#50 — the server widgets: gauges said in words, the storage's disks with their share, a disk
// in trouble and the containers with an update; on a single row, one line each.

const show = (key: string, data: unknown, compact = false) => {
  const Widget = widgetComponent(key);
  if (!Widget) throw new Error(`no ${key}`);
  return render(
    <MemoryRouter>
      <Widget payload={{ state: "available", data } as never} config={{}} compact={compact} />
    </MemoryRouter>,
  );
};

describe("server widgets", () => {
  it("shows the server's gauges and what needs attention", () => {
    show("health.host", {
      name: "Glances",
      hostname: "Tower",
      cpu: 23.4,
      memory: { used: 76, total: 100 },
      storage: { used: 60, total: 100 },
      temperature: { label: "Core 0", value: 52 },
      containers: { running: 108, total: 109 },
      updates: 3,
      warnings: ["disk_errors"],
    });
    expect(screen.getByRole("img", { name: "CPU: 23 %" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Memory: 76 %" })).toBeInTheDocument();
    expect(screen.getByText("Disk errors")).toBeInTheDocument();
    expect(screen.getByText(/108 of 109 running · 3 updates/)).toBeInTheDocument();
  });

  it("lists the disks and says a stopped array", () => {
    show("health.storage", {
      name: "Unraid",
      storage: { used: 900, total: 1000 },
      array_state: "STOPPED",
      volumes: [
        { name: "disk1", kind: "disk", used: 98, total: 100, ok: true, temperature: 33 },
        { name: "parity", kind: "parity", used: null, total: 100, ok: false },
      ],
      warnings: ["array_stopped"],
    });
    expect(screen.getByText("Array stopped")).toBeInTheDocument();
    expect(screen.getByText("98 %")).toBeInTheDocument();
    expect(screen.getByText("parity", { selector: ".storage-widget__parity" })).toBeInTheDocument();
  });

  it("says the containers on one row", () => {
    show(
      "health.containers",
      { name: "Unraid", running: 2, total: 3, updates: 1, updates_known: true, items: [], notices: [] },
      true,
    );
    expect(screen.getByText("2 of 3 running")).toBeInTheDocument();
    expect(screen.getByText("1 update")).toBeInTheDocument();
  });
});
