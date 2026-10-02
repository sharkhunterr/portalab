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
    chunkSizeWarningLimit: 600, // the shared vendor chunk (React, Radix, TanStack, zod) is ~540 kB
    rollupOptions: {
      output: {
        // third-party code in long-cached chunks, the i18n runtime (react-intl, formatjs) apart (spec 026)
        manualChunks: (id) => {
          if (!id.includes("/node_modules/")) return undefined;
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
