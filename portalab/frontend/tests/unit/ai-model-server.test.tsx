import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

// Issue 169 — the assistant's model server: the Ollama services are offered; choosing one points the
// assistant at its OpenAI-compatible address and picks a model in memory that can use tools; the models
// say their size, what is loaded and when one cannot use tools.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  requests: [] as Request[],
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  installed.requests = fake.requests;
  return importOriginal();
});

import { ModelServer } from "../../src/features/ai/admin/ModelServer";
import { json } from "../support/fake-api";

const SERVERS = [
  {
    service_id: "s1",
    name: "PC-IA",
    connector: "ollama",
    endpoint: "http://192.168.1.60:11434/v1",
    state: "ok",
    models: [
      {
        name: "mistral:7b",
        family: "llama",
        parameters: "7.2B",
        quantization: "Q4_K_M",
        size_bytes: 4e9,
        loaded: false,
        vram_bytes: null,
        embedding: false,
        tools: false,
      },
      {
        name: "qwen3:8b",
        family: "qwen3",
        parameters: "8.2B",
        quantization: "Q4_K_M",
        size_bytes: 5e9,
        loaded: true,
        vram_bytes: 6442450944,
        embedding: false,
        tools: true,
      },
      {
        name: "nomic-embed-text:latest",
        family: "nomic-bert",
        parameters: null,
        quantization: null,
        size_bytes: 2e8,
        loaded: false,
        vram_bytes: null,
        embedding: true,
        tools: null,
      },
    ],
  },
];

let latest: Record<string, unknown> = {};
function Harness() {
  const [values, setValues] = useState<Record<string, unknown>>({
    provider_endpoint: "",
    provider_model: "",
  });
  latest = values;
  return <ModelServer values={values} onChange={setValues} />;
}

describe("the assistant's model server", () => {
  it("points the assistant at an Ollama service and one of its models", async () => {
    fake.handler = () => json(200, SERVERS);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Harness />
      </QueryClientProvider>,
    );
    const server = await screen.findByLabelText("Server");
    fireEvent.change(server, { target: { value: "s1" } });
    expect(latest).toMatchObject({
      provider_endpoint: "http://192.168.1.60:11434/v1",
      provider_model: "qwen3:8b",
    });
    const model = screen.getByLabelText("Model") as HTMLSelectElement;
    const options = Array.from(model.options).map((o) => o.textContent);
    expect(options).toEqual([
      "mistral:7b · 7.2B · Q4_K_M · no tools",
      "qwen3:8b · 8.2B · Q4_K_M · in memory (6 GB)",
    ]);
    expect(screen.getByText("In memory now: qwen3:8b (6 GB)")).toBeTruthy();
    fireEvent.change(model, { target: { value: "mistral:7b" } });
    expect(latest.provider_model).toBe("mistral:7b");
    expect(screen.getByText(/cannot use tools/)).toBeTruthy();
  });
});
