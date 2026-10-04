import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The backend serves the built SPA as static files (single image, spec 001 R14).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/healthz": "http://localhost:8080",
      "/readyz": "http://localhost:8080",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    // the shared vendor chunk (React, Radix, TanStack, zod) is ~540 kB; Mermaid (core ~620 kB, some diagram types ~690 kB) is only
    // fetched when a page actually contains a diagram (spec 011)
    chunkSizeWarningLimit: 700,
    // fonts are always separate files: the CSP (``font-src 'self'``) refuses ``data:`` fonts (spec 027)
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf)$/.test(file) ? false : undefined),
    rollupOptions: {
      output: {
        // third-party code in long-cached chunks, the i18n runtime (react-intl, formatjs) apart (spec 026)
        manualChunks: (id) => {
          if (!id.includes("/node_modules/")) return undefined;
          // Mermaid (spec 011) and its dependencies load on demand only: let Rollup split them lazily
          if (
            /node_modules\/(mermaid|@mermaid-js|cytoscape[a-z-]*|cose-base|layout-base|dagre-d3-es|katex|khroma|@chevrotain|chevrotain|langium|roughjs|hachure-fill|points-on-curve|points-on-path|path-data-parser|stylis|lodash-es|dayjs|marked|dompurify|@braintree|@iconify|@upsetjs|ts-dedent|d3|delaunator|robust-predicates|tinyexec|uuid)\//.test(
              id,
            )
          )
            return undefined;
          if (
            /node_modules\/(recharts|d3-[a-z-]+|victory-vendor|decimal\.js-light|react-redux|@reduxjs|redux|reselect|immer|es-toolkit|eventemitter3)\//.test(
              id,
            )
          )
            return "charts";
          return /node_modules\/(react-intl|intl-messageformat|@formatjs)\//.test(id) ? "intl" : "vendor";
        },
      },
    },
  },
  // pre-bundled up front so the dev server never reloads mid-session (stable a11y journeys)
  optimizeDeps: {
    include: [
      "@radix-ui/react-dialog",
      "@radix-ui/react-dropdown-menu",
      "@radix-ui/react-popover",
      "@radix-ui/react-slot",
      "@radix-ui/react-tabs",
      "@radix-ui/react-tooltip",
      "@formatjs/icu-messageformat-parser",
      "@formatjs/icu-messageformat-parser/printer.js",
      "@tanstack/react-query",
      "class-variance-authority",
      "intl-messageformat",
      "lucide-react",
      "openapi-fetch",
      "react-intl",
      "zod",
    ],
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/a11y/**/*.test.{ts,tsx}"],
  },
});
