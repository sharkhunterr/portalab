import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 265: a question of the games (its prompt, its choices, its order), as the server gives it.

vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  installFakeApi();
  return importOriginal();
});

import type { Question } from "../../../src/features/games/api";
import { QuestionView } from "../../../src/features/games/QuestionView";

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element }], { initialEntries: ["/"] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const now = new Date().toISOString();

afterEach(() => cleanup());

describe("issue 265 — the games", () => {
  it("asks a question and sends the choice made", async () => {
    const onAnswer = vi.fn();
    const question: Question = {
      game: "casting",
      prompt: { kind: "movie", people: [{ name: "Sigourney Weaver", image: null }] },
      choices: [
        { id: "a1", label: "Alien (1979)" },
        { id: "b2", label: "Heat (1995)" },
      ],
      ordered: false,
      image: false,
      audio: false,
    };
    show(
      <QuestionView
        question={question}
        base="/x"
        started={now}
        seconds={20}
        skew={0}
        phase="question"
        onAnswer={onAnswer}
      />,
    );
    expect(await screen.findByText("Which title do they play in?")).toBeTruthy();
    expect(screen.getByText("Sigourney Weaver")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Alien (1979)" }));
    expect(onAnswer).toHaveBeenCalledWith({ choice: "a1" });
  });

  it("tells the right answer once revealed", async () => {
    const question: Question = {
      game: "poster",
      prompt: { kind: "movie" },
      choices: [
        { id: "a1", label: "Alien (1979)" },
        { id: "b2", label: "Heat (1995)" },
      ],
      ordered: false,
      image: true,
      audio: false,
    };
    show(
      <QuestionView
        question={question}
        base="/api/v1/games/sessions/s1"
        round={3}
        started={now}
        seconds={20}
        skew={0}
        phase="reveal"
        given="b2"
        answer="a1"
        reveal={{ title: "Alien", year: 1979 }}
        mine={{ correct: false, points: 0, given: "b2" }}
      />,
    );
    const image = (await screen.findByAltText("A blurred scene to recognise")) as HTMLImageElement;
    // the round in the address (never the browser's last image), sharp once answered
    expect(image.src).toContain("/api/v1/games/sessions/s1/image?round=3&step=5");
    expect(screen.getByRole("button", { name: "Alien (1979)" }).getAttribute("data-state")).toBe("right");
    expect(screen.getByRole("button", { name: "Heat (1995)" }).getAttribute("data-state")).toBe("wrong");
  });

  it("asks each question's theme tune by its round — never the first one again", async () => {
    const question: Question = {
      game: "blindtest",
      prompt: { kind: "series" },
      choices: [
        { id: "a1", label: "Lost" },
        { id: "b2", label: "Dexter" },
      ],
      ordered: false,
      image: false,
      audio: true,
    };
    const props = { question, base: "/x", started: now, seconds: 20, skew: 0, phase: "question" as const };
    const first = show(<QuestionView {...props} round={1} />);
    await screen.findByText("Which series has this theme?");
    expect(first.container.querySelector("audio")?.getAttribute("src")).toBe("/x/audio?round=1");
    cleanup();
    const second = show(<QuestionView {...props} round={2} />);
    await screen.findByText("Which series has this theme?");
    expect(second.container.querySelector("audio")?.getAttribute("src")).toBe("/x/audio?round=2");
  });

  it("answers with the keyboard: 2 is the second choice", async () => {
    const onAnswer = vi.fn();
    const question: Question = {
      game: "casting",
      prompt: { kind: "movie", people: [] },
      choices: [
        { id: "a1", label: "Alien (1979)" },
        { id: "b2", label: "Heat (1995)" },
      ],
      ordered: false,
      image: false,
      audio: false,
    };
    show(
      <QuestionView
        question={question}
        base="/x"
        started={now}
        seconds={20}
        skew={0}
        phase="question"
        onAnswer={onAnswer}
      />,
    );
    await screen.findByText("Which title do they play in?");
    fireEvent.keyDown(window, { key: "2" });
    expect(onAnswer).toHaveBeenCalledWith({ choice: "b2" });
  });

  it("puts titles in order, then sends the order", async () => {
    const onAnswer = vi.fn();
    const question: Question = {
      game: "timeline",
      prompt: { count: 3 },
      choices: [
        { id: "x", label: "Heat" },
        { id: "y", label: "Alien" },
        { id: "z", label: "Dune" },
      ],
      ordered: true,
      image: false,
      audio: false,
    };
    show(
      <QuestionView
        question={question}
        base="/x"
        started={now}
        seconds={45}
        skew={0}
        phase="question"
        onAnswer={onAnswer}
      />,
    );
    // issue 269: on a timeline, moved by their arrows (or dragged), then sent as they stand
    await screen.findByText("Oldest");
    fireEvent.click(screen.getByRole("button", { name: "Move « Alien » up" }));
    expect(screen.getByText("« Alien » now 1st")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Move « Alien » up" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onAnswer).toHaveBeenCalledWith({ order: ["y", "x", "z"] });
  });

  it("sends a timeline as it stands when the time runs out, then shows the right one and where I had them", async () => {
    const onAnswer = vi.fn();
    const question: Question = {
      game: "timeline",
      prompt: { count: 3 },
      choices: [
        { id: "x", label: "Heat" },
        { id: "y", label: "Alien" },
        { id: "z", label: "Dune" },
      ],
      ordered: true,
      image: false,
      audio: false,
    };
    const props = { question, base: "/x", seconds: 45, skew: 0, onAnswer };
    const late = new Date(Date.now() - 46_000).toISOString();
    // rendered alone (no router): the same question rendered again keeps what was moved
    const { rerender } = render(<QuestionView {...props} started={now} phase="question" />);
    fireEvent.click(await screen.findByRole("button", { name: "Move « Dune » up" }));
    expect(onAnswer).not.toHaveBeenCalled();
    rerender(<QuestionView {...props} started={late} phase="question" />);
    expect(onAnswer).toHaveBeenCalledWith({ order: ["x", "z", "y"] });

    rerender(
      <QuestionView
        {...props}
        started={late}
        phase="reveal"
        given={["x", "z", "y"]}
        answer={["y", "x", "z"]}
        reveal={{ values: { x: 1995, y: 1979, z: 2021 } }}
      />,
    );
    const lines = screen.getAllByRole("listitem");
    expect(lines.map((l) => l.getAttribute("data-right"))).toEqual(["false", "false", "false"]);
    expect(lines[0]?.textContent).toContain("1979");
    expect(screen.getByText("You had it 3rd")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Send" })).toBeNull();
  });
});
