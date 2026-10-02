// spec 026 T010 — frontend side of the catalog checks (same rules as ``portalab i18n check``): every
// bundle under backend/locales parses as ICU MessageFormat (formatjs, the runtime parser of the SPA), every
// translation has the English source's placeholders, and no key is missing or unused.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parse, TYPE } from "@formatjs/icu-messageformat-parser";

const ROOT = new URL("../../backend/locales/", import.meta.url).pathname;
const SOURCE = "en";

function argumentsOf(elements, names = new Set()) {
  for (const element of elements) {
    if (element.type !== TYPE.literal && element.type !== TYPE.pound && typeof element.value === "string")
      names.add(element.value);
    if (element.options)
      for (const option of Object.values(element.options)) argumentsOf(option.value, names);
    if (element.children) argumentsOf(element.children, names);
  }
  return names;
}

const catalogs = {};
for (const language of readdirSync(ROOT)) {
  for (const file of readdirSync(join(ROOT, language)).filter((f) => f.endsWith(".json"))) {
    catalogs[language] ??= {};
    catalogs[language][file.replace(/\.json$/, "")] = JSON.parse(
      readFileSync(join(ROOT, language, file), "utf8"),
    );
  }
}

const problems = [];
const same = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));
for (const [language, namespaces] of Object.entries(catalogs)) {
  for (const [namespace, messages] of Object.entries(namespaces)) {
    const reference = catalogs[SOURCE]?.[namespace] ?? {};
    for (const [key, message] of Object.entries(messages)) {
      let names;
      try {
        names = argumentsOf(parse(message));
      } catch (error) {
        problems.push(`${language}/${namespace}:${key}: invalid ICU message (${error.message})`);
        continue;
      }
      if (language === SOURCE) continue;
      if (!(key in reference)) {
        problems.push(`${language}/${namespace}:${key}: unused (not in ${SOURCE})`);
        continue;
      }
      const expected = argumentsOf(parse(reference[key]));
      if (!same(names, expected))
        problems.push(
          `${language}/${namespace}:${key}: placeholders [${[...names]}] != ${SOURCE} [${[...expected]}]`,
        );
    }
    if (language !== SOURCE)
      for (const key of Object.keys(reference).filter((k) => !(k in messages)))
        problems.push(`${language}/${namespace}:${key}: missing translation`);
  }
}

if (problems.length) {
  for (const problem of problems) console.error(`✗ ${problem}`);
  process.exit(1);
}
console.log(`i18n check: ${Object.keys(catalogs).length} languages, no problem`);
