const API = process.env.API_URL || "http://127.0.0.1:8787";
/** @type {import('next').NextConfig} */
export default {
  async rewrites() {
    return [
      {source: "/api/:path*", destination: `${API}/api/:path*`},
      {source: "/media/:path*", destination: `${API}/media/:path*`},
    ];
  },
};
