import type { NextConfig } from "next";

const FLASK_API = (
  process.env.FLASK_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "https://satori-1deg.onrender.com"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // ── Dev proxy: forward /api/* and /health to Flask ────────────────────
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${FLASK_API}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${FLASK_API}/health`,
      },
    ];
  },
};

export default nextConfig;
