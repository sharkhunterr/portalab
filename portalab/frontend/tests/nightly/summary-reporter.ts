import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import type { FullResult, Reporter, TestCase, TestResult } from "@playwright/test/reporter";

/**
 * Issue 469: the morning's report — what failed, grouped by what the shop sells (the test's first words:
 * « interface vhs », « widget media.stats »…), each with its device and its first problems.
 */
/** A terminal's colors taken out of a message (ESC [ … m). */
function stripAnsi(text: string): string {
  return text
    .split(String.fromCharCode(27))
    .map((part, i) => (i ? part.replace(/^\[[0-9;]*m/, "") : part))
    .join("");
}

export default class SummaryReporter implements Reporter {
  private readonly failed = new Map<string, string[]>();
  private passed = 0;
  private flaky = 0;

  constructor(private readonly options: { outputFile: string }) {}

  onTestEnd(test: TestCase, result: TestResult) {
    if (result.status === "passed") {
      if (result.retry > 0) this.flaky += 1;
      else this.passed += 1;
      return;
    }
    if (result.status === "skipped" || result.retry < test.retries) return;
    const [subject = test.title] = test.title.split(" — ");
    const device = test.parent.project()?.name ?? "";
    const lines = result.errors
      .flatMap((e) => (e.message ?? "").split("\n"))
      .map((l) => stripAnsi(l).trim())
      .filter((l) => /^(\+ +"|Error|Expected:|Received:)/.test(l))
      .slice(0, 12);
    const list = this.failed.get(subject) ?? [];
    list.push(`- **${device}** ${test.title}\n${lines.map((l) => `  ${l}`).join("\n")}`);
    this.failed.set(subject, list);
  }

  onEnd(result: FullResult) {
    const rows = [...this.failed.entries()].sort(([a], [b]) => a.localeCompare(b));
    const text = [
      `# Nightly regression — ${new Date().toISOString().slice(0, 16)} — ${result.status}`,
      "",
      `${this.passed} passed, ${this.flaky} passed on retry, ${rows.reduce((n, [, l]) => n + l.length, 0)} failed.`,
      "",
      ...rows.flatMap(([subject, list]) => [`## ${subject}`, "", ...list, ""]),
    ].join("\n");
    mkdirSync(dirname(this.options.outputFile), { recursive: true });
    writeFileSync(this.options.outputFile, text);
  }
}
