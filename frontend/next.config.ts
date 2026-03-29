import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://akhil-008-formulai-backend-api.hf.space",
  },
};

export default nextConfig;
