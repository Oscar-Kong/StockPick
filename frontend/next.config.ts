import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Avoid picking ~/package-lock.json as the workspace root during build tracing.
  outputFileTracingRoot: path.join(frontendDir, ".."),
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
