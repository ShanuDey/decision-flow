import path from "node:path";

import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

const dev = process.env.NODE_ENV !== "production";

// One .env at the repo root feeds both the API and the web app; Next caches its own load, so force.
loadEnvConfig(path.resolve(process.cwd(), ".."), dev, console, true);

const DOCS_ORIGIN =
  process.env.DOCS_ORIGIN ?? (dev ? "http://localhost:4321" : "https://shanudey.github.io/decision-flow/embed");

// /docs compiles its WebAssembly search index and may be framed by the editor.
const csp = (docs: boolean) => [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${docs ? " 'wasm-unsafe-eval'" : ""}${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws: wss:" : ""}`,
  `frame-ancestors ${docs ? "'self'" : "'none'"}`,
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = (docs: boolean) => [
  { key: "Content-Security-Policy", value: csp(docs) },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: docs ? "SAMEORIGIN" : "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      // GitHub Pages only serves the docs index at the trailing-slash URL; the dev server only without.
      { source: "/docs", destination: `${DOCS_ORIGIN}/docs${dev ? "" : "/"}` },
      { source: "/docs/:path*", destination: `${DOCS_ORIGIN}/docs/:path*` },
    ];
  },
  async headers() {
    return [
      { source: "/((?!docs(?:/|$)).*)", headers: securityHeaders(false) },
      { source: "/docs/:path*", headers: securityHeaders(true) },
    ];
  },
};

export default nextConfig;
