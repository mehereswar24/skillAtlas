import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this directory.
  //
  // Turbopack infers the root from the nearest lockfile, and there is a stray
  // package-lock.json in the home directory — so it picked `C:\Users\<user>`
  // and resolved this project by a path relative to that. With a second copy
  // of the app also under home, the two shared a cache key and poisoned each
  // other: the dev server served chunks referring to the *other* checkout's
  // node_modules and threw "Cannot find module" for packages that were plainly
  // installed. Pinning the root is what stops that.
  turbopack: {
    root: __dirname,
  },
  allowedDevOrigins: ['127.0.0.1', 'localhost', 'blake-charge-recognized-minolta.trycloudflare.com'],
  devIndicators: {
    position: 'bottom-right',
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
    ],
  },
};

export default nextConfig;
