/** @type {import('next').NextConfig} */
const nextConfig = {
  // Use standalone for dev rewrites, static export for production
  ...(process.env.NODE_ENV === "production"
    ? { output: "export", trailingSlash: true }
    : {}),
  images: { unoptimized: true },
  async rewrites() {
    // In development, proxy API calls to FastAPI backend
    if (process.env.NODE_ENV !== "production") {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;
