import { useMemo } from "react";
import { type Translate, useT } from "./useT";

/**
 * Issue 201: a screen's English strings object read from the catalogs, in the member's language. Each text
 * is the message ``<scope>.<path>`` (``account:auth.loginTitle``, ``account:auth.visibility.public``); a
 * function is a message whose placeholders are its arguments, named in ``args`` by path
 * (``{ throttled: ["seconds"] }``). The object keeps its English shape, so the screens read it unchanged —
 * outside a provider (tests, first paint) the catalogs' bundled English is used.
 */
export type StringArgs = Record<string, readonly string[]>;

type Value = string | number;

export function localizeStrings<T extends object>(
  defaults: T,
  t: Translate,
  scope: string,
  args: StringArgs,
): T {
  const walk = (node: unknown, path: string): unknown => {
    if (typeof node === "string") return t(`${scope}.${path}`);
    if (typeof node === "function") {
      const names = args[path] ?? [];
      return (...values: Value[]) =>
        t(`${scope}.${path}`, Object.fromEntries(names.map((name, index) => [name, values[index] ?? ""])));
    }
    if (node && typeof node === "object")
      return Object.fromEntries(
        Object.entries(node).map(([key, value]) => [key, walk(value, path ? `${path}.${key}` : key)]),
      );
    return node;
  };
  return walk(defaults, "") as T;
}

export function useStrings<T extends object>(defaults: T, scope: string, args: StringArgs = {}): T {
  const t = useT();
  // biome-ignore lint/correctness/useExhaustiveDependencies: the defaults and their arguments are constants
  return useMemo(() => localizeStrings(defaults, t, scope, args), [t, scope]);
}
