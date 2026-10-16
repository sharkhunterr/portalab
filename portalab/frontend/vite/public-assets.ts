import type { OutputBundle, OutputChunk } from "rollup";
import type { Plugin } from "vite";

/**
 * 028 (issue 135): the static files a visitor may load — the sign-in page's. Written to
 * ``public-assets.json`` beside ``index.html``; the server serves every other script of the application to
 * signed-in members only (stylesheets, fonts, images and sounds stay readable: no code in them).
 *
 * The sign-in page is the entry chunk and what it imports statically; every page loaded lazily (the
 * administration, the shop, the dashboard…) is left out.
 */
export function publicAssets(): Plugin {
  return {
    name: "portalab-public-assets",
    apply: "build",
    generateBundle(_options, bundle: OutputBundle) {
      const chunks = new Map<string, OutputChunk>();
      for (const output of Object.values(bundle))
        if (output.type === "chunk") chunks.set(output.fileName, output);
      const open = new Set<string>();
      const visit = (name: string) => {
        if (open.has(name)) return;
        open.add(name);
        const chunk = chunks.get(name);
        if (!chunk) return;
        for (const imported of chunk.imports) visit(imported);
        const meta = (
          chunk as OutputChunk & { viteMetadata?: { importedCss: Set<string>; importedAssets: Set<string> } }
        ).viteMetadata;
        for (const css of meta?.importedCss ?? []) open.add(css);
        for (const asset of meta?.importedAssets ?? []) open.add(asset);
      };
      for (const chunk of chunks.values()) if (chunk.isEntry) visit(chunk.fileName);
      for (const output of Object.values(bundle)) {
        if (output.type === "asset" && !/\.m?js$/.test(output.fileName)) open.add(output.fileName);
      }
      const names = [...open]
        .filter((name) => name.startsWith("assets/"))
        .map((name) => name.slice("assets/".length))
        .sort();
      this.emitFile({ type: "asset", fileName: "public-assets.json", source: `${JSON.stringify(names)}\n` });
    },
  };
}
