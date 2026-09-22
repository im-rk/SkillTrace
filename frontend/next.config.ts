import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A self-contained server bundle (node_modules pruned to only what's actually used),
  // run via `node server.js` -- what infra/docker/frontend.Dockerfile builds and ships.
  // Opt-in only: it's not meant to be combined with `next start` (Next warns if it is),
  // which local dev/lint/build/e2e all use, so it stays off unless the Docker build asks.
  output: process.env.NEXT_OUTPUT_STANDALONE === "true" ? "standalone" : undefined,
};

export default nextConfig;
