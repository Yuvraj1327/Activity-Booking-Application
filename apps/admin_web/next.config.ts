import type { NextConfig } from "next";
import pkg from "./package.json";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Re-opening a page you visited in the last 30 s is instant. Saving changes still refreshes data
  // (server actions revalidate), and signing in/out reloads the router cache.
  experimental: { staleTimes: { dynamic: 30, static: 180 } },
  devIndicators: false, // hides the floating Next.js "N" badge in development
  env: { NEXT_PUBLIC_APP_VERSION: pkg.version },
};

export default nextConfig;
