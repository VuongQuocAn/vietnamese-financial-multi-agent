import type { NextConfig } from "next";

const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

const config: NextConfig = {
  // Allow the PDF byte limit plus multipart headers through the same-origin proxy.
  experimental: {
    proxyClientMaxBodySize:
      Number(process.env.WEB_MAX_UPLOAD_BYTES ?? 50 * 1024 * 1024) + 65536,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default config;
