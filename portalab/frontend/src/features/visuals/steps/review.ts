import type { Confirmations, ElementReport, VersionDetail } from "../api";

/** What a version needs confirmed before it is published: its scripts, each look it takes over, each data
 * contract a widget asks for. */
export function confirmationsNeeded(detail: VersionDetail): {
  scripts: boolean;
  replaces: string[];
  contracts: string[];
} {
  const replaces = detail.report.items
    .filter((i) => i.code === "look.replaces" || i.code === "look.replaces_builtin")
    .map((i) => {
      const element = detail.report.elements.find((e) => e.product === i.element);
      return element?.look ? `${element.type}:${element.look}` : null;
    })
    .filter((x): x is string => Boolean(x));
  const contracts = [...new Set(detail.report.elements.flatMap((e: ElementReport) => e.contracts ?? []))];
  return { scripts: detail.report.summary.script, replaces: [...new Set(replaces)], contracts };
}

export function missingConfirmations(detail: VersionDetail, given: Partial<Confirmations>): string[] {
  const needed = confirmationsNeeded(detail);
  return [
    ...(needed.scripts && !given.scripts ? ["scripts"] : []),
    ...needed.replaces.filter((r) => !(given.replaces ?? []).includes(r)),
    ...needed.contracts.filter((c) => !(given.contracts ?? []).includes(c)),
  ];
}

/** 028 (US6): what the administrator may give everyone rather than sell (no shop product). */
export const GIVEABLE = new Set(["widget", "widget_style", "widget_option"]);

export const NOT_SOLD = new Set([
  "navigation",
  "booster_scene",
  "booster_look",
  "booster_opening",
  "card_reveal",
  "card_face",
  "card_back",
]);
