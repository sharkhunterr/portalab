import { describe, expect, it } from "vitest";
import { publicAssets } from "../../../vite/public-assets";

// 028 (issue 135, SC-005): a visitor may load the sign-in page's files and nothing else of the application's
// code — not a lazy page, nor the source map telling it.

const chunk = (fileName: string, isEntry: boolean, imports: string[] = [], css: string[] = []) => ({
  type: "chunk",
  fileName,
  isEntry,
  imports,
  viteMetadata: { importedCss: new Set(css), importedAssets: new Set<string>() },
});
const asset = (fileName: string) => ({ type: "asset", fileName });

describe("public assets", () => {
  it("opens the sign-in closure, its maps and the code-free files only", () => {
    const bundle = Object.fromEntries(
      [
        chunk("assets/index-a.js", true, ["assets/vendor-b.js"], ["assets/index-a.css"]),
        chunk("assets/vendor-b.js", false),
        chunk("assets/AdminPage-c.js", false),
        asset("assets/index-a.js.map"),
        asset("assets/vendor-b.js.map"),
        asset("assets/AdminPage-c.js.map"),
        asset("assets/index-a.css"),
        asset("assets/inter.woff2"),
      ].map((output) => [output.fileName, output]),
    );
    let written = "";
    const plugin = publicAssets() as unknown as {
      generateBundle: (this: { emitFile: (f: { source: string }) => void }, o: unknown, b: unknown) => void;
    };
    plugin.generateBundle.call(
      {
        emitFile: (file) => {
          written = file.source;
        },
      },
      {},
      bundle,
    );
    const names = JSON.parse(written) as string[];
    expect(names).toEqual([
      "index-a.css",
      "index-a.js",
      "index-a.js.map",
      "inter.woff2",
      "vendor-b.js",
      "vendor-b.js.map",
    ]);
    expect(names).not.toContain("AdminPage-c.js");
    expect(names).not.toContain("AdminPage-c.js.map");
  });
});
