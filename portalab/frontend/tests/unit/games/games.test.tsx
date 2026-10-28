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
    expect(image.src).toContain("/api/v1/games/sessions/s1/image?step=5"); // sharp once answered
    expect(screen.getByRole("button", { name: "Alien (1979)" }).getAttribute("data-state")).toBe("right");
    expect(screen.getByRole("button", { name: "Heat (1995)" }).getAttribute("data-state")).toBe("wrong");
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
    const send = await screen.findByRole("button", { name: "Send" });
    expect((send as HTMLButtonElement).disabled).toBe(true);
    for (const title of ["Alien", "Heat", "Dune"])
      fireEvent.click(screen.getByRole("button", { name: title }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onAnswer).toHaveBeenCalledWith({ order: ["y", "x", "z"] });
  });
});
