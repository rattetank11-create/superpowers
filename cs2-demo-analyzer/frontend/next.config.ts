import type { NextConfig } from "next";

// В проде /api/* проксирует Caddy прямо в backend.
// В разработке (`npm run dev`) Next сам проксирует /api/* на BACKEND_URL.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [{ source: "/api/:path*", destination: `${backend}/api/:path*` }]
      : [];
  },
};

export default config;
