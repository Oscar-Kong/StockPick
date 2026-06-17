import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/penny", destination: "/scan?bucket=penny", permanent: true },
      { source: "/compounder", destination: "/scan?bucket=compounder", permanent: true },
      { source: "/medium", destination: "/scan?bucket=penny", permanent: true },
      { source: "/scans", destination: "/library?tab=scans", permanent: true },
      { source: "/trades", destination: "/?journal=1#home-journal", permanent: true },
      { source: "/watchlist", destination: "/workspace", permanent: true },
      { source: "/reports", destination: "/library?tab=reports", permanent: true },
    ];
  },
};

export default nextConfig;
