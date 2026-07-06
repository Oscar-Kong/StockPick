import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));

const backendProxyUrl = (
  process.env.BACKEND_URL?.trim() ||
  process.env.NEXT_PUBLIC_API_URL?.trim() ||
  "http://127.0.0.1:18731"
).replace(/\/$/, "");

/** First-path segments served by the FastAPI backend (relative fetches when NEXT_PUBLIC_API_URL is unset). */
const BACKEND_PATH_PREFIXES = [
  "api",
  "research",
  "health",
  "settings",
  "watchlist",
  "analyze",
  "saved",
  "trader-intel",
  "trades",
  "portfolio",
  "data",
  "ml",
  "lean",
  "explain",
  "backtest",
  "brokerage",
  "home",
  "scan",
  "allocation",
  "ops",
  "stock",
] as const;

const nextConfig: NextConfig = {
  // Avoid picking ~/package-lock.json as the workspace root during build tracing.
  outputFileTracingRoot: path.join(frontendDir, ".."),
  async rewrites() {
    return BACKEND_PATH_PREFIXES.flatMap((prefix) => [
      { source: `/${prefix}`, destination: `${backendProxyUrl}/${prefix}` },
      { source: `/${prefix}/:path*`, destination: `${backendProxyUrl}/${prefix}/:path*` },
    ]);
  },
  async redirects() {
    return [
      { source: "/penny", destination: "/scan?bucket=penny", permanent: true },
      { source: "/compounder", destination: "/scan?bucket=compounder", permanent: true },
      { source: "/medium", destination: "/scan?bucket=penny", permanent: true },
      { source: "/scans", destination: "/library?tab=scans", permanent: true },
      { source: "/portfolio", destination: "/?tab=research", permanent: true },
      { source: "/trades", destination: "/?tab=activity", permanent: true },
      { source: "/watchlist", destination: "/workspace", permanent: true },
      { source: "/reports", destination: "/library?tab=reports", permanent: true },
    ];
  },
};

export default nextConfig;
