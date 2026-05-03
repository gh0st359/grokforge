/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const core = process.env.CORE_URL || "http://localhost:8080";
    return [
      { source: "/api/core/:path*", destination: `${core}/:path*` },
    ];
  },
};
module.exports = nextConfig;
