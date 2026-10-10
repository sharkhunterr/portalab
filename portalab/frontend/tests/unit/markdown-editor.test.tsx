import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { applyTool } from "../../src/features/content/MarkdownEditor";
import { ListTemplate } from "../../src/features/dashboard/templates/Templates";

// #48 — the editor's toolbar writes the Markdown around the selection (and a second click on a line
// tool undoes it); a widget line not read yet carries a dot said in words.

const bold = { key: "bold", icon: "bold", before: "**", after: "**", placeholder: "bold" };
const bullets = { key: "bullets", icon: "list", before: "- ", line: true, placeholder: "Item" };
const numbers = { key: "numbers", icon: "list", before: "1. ", line: true, placeholder: "Item" };

describe("markdown toolbar", () => {
  it("wraps the selection, or a placeholder, and selects what it wrapped", () => {
    expect(applyTool("make it loud", 8, 12, bold)).toEqual({ text: "make it **loud**", start: 10, end: 14 });
    expect(applyTool("x ", 2, 2, bold)).toEqual({ text: "x **bold**", start: 4, end: 8 });
  });

  it("prefixes every selected line, numbers them, and undoes a second time", () => {
    const listed = applyTool("one\ntwo", 0, 7, bullets);
    expect(listed.text).toBe("- one\n- two");
    expect(applyTool(listed.text, 0, listed.text.length, bullets).text).toBe("one\ntwo");
    expect(applyTool("a\nb\nc", 0, 5, numbers).text).toBe("1. a\n2. b\n3. c");
  });
});

describe("unread", () => {
  it("marks a line not read yet", () => {
    render(
      <MemoryRouter>
        <ListTemplate
          payload={
            {
              state: "available",
              data: {
                items: [
                  { title: "Fresh", route: "/news/fresh", unread: true },
                  { title: "Old", route: "/news/old", unread: false },
                ],
              },
            } as never
          }
          config={{}}
        />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("img", { name: "Not read yet" })).toHaveLength(1);
    expect(screen.getByText("Fresh").closest("li")?.dataset.unread).toBe("true");
  });
});
