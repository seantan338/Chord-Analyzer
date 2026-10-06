import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for Docker / Zeabur deployments.
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
