import {
  isLiteralElement,
  isPluralElement,
  isSelectElement,
  isTagElement,
  type MessageFormatElement,
  parse,
} from "@formatjs/icu-messageformat-parser";
import { printAST } from "@formatjs/icu-messageformat-parser/printer.js";

/**
 * Pseudo-locales (spec 026 T027; R7): ``en-XA`` accents and lengthens literal text to reveal truncation
 * and hard-coded strings; ``ar-XB`` wraps it in right-to-left overrides to exercise mirroring. Only literal
 * text changes — arguments, plural/select branches' syntax and tags stay intact (text inside branches is
 * pseudo-translated too).
 */
export type PseudoLocale = "en-XA" | "ar-XB";

const ACCENTS: Record<string, string> = {
  a: "à",
  e: "é",
  i: "î",
  o: "ö",
  u: "ü",
  y: "ý",
  c: "ç",
  n: "ñ",
  A: "À",
  E: "É",
  I: "Î",
  O: "Ö",
  U: "Ü",
};

function accent(text: string): string {
  return [...text].map((char) => ACCENTS[char] ?? char).join("");
}

function walk(elements: MessageFormatElement[]): void {
  for (const element of elements) {
    if (isLiteralElement(element)) element.value = accent(element.value);
    else if (isPluralElement(element) || isSelectElement(element))
      for (const option of Object.values(element.options)) walk(option.value);
    else if (isTagElement(element)) walk(element.children);
  }
}

export function pseudoMessage(message: string, code: PseudoLocale): string {
  if (code === "ar-XB") return `\u202e${message}\u202c`;
  try {
    const ast = parse(message);
    walk(ast);
    return `[${printAST(ast)} ~~~]`;
  } catch {
    return `[${accent(message)} ~~~]`;
  }
}

export function pseudoCatalog(messages: Record<string, string>, code: PseudoLocale): Record<string, string> {
  return Object.fromEntries(
    Object.entries(messages).map(([key, value]) => [key, pseudoMessage(value, code)]),
  );
}
