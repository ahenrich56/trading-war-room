import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    resolveAlias: {
      // Turbopack doesn't support the "style" export condition in package.json
      // so we resolve these CSS imports to their actual file paths
      "shadcn/tailwind.css": "shadcn/dist/tailwind.css",
      "tw-animate-css": "tw-animate-css/dist/tw-animate.css",
    },
  },
};

export default nextConfig;
