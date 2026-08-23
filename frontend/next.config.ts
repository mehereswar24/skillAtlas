import type { NextConfig } from "next";

/**
 * Security headers for the rendered app.
 *
 * These are the ones that matter for a browser: the API sets its own, stricter
 * set (`backend/app/middleware/security.py`), but the browser never talks to
 * the API directly — it talks to this BFF.
 *
 * Content-Security-Policy is deliberately NOT here. It carries a per-request
 * nonce so that Next's inline bootstrap scripts can run, and a static
 * `headers()` entry cannot hold a per-request value — so it is built in
 * `src/proxy.ts` instead. Adding a second CSP here would not merge with that
 * one; the browser enforces every policy it is sent, so the intersection of
 * the two would apply and the nonce would stop mattering.
 */
const securityHeaders = [
  // Stop a browser second-guessing Content-Type and executing an upload as script.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Clickjacking: nothing here is meant to be framed by another site.
  { key: "X-Frame-Options", value: "DENY" },
  // Send the origin to third parties, never the full path — concept and
  // company URLs would otherwise leak what a user is studying.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
];

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle with only the node_modules actually
  // reached. This is what lets the production image copy a ~100MB output
  // instead of the ~1GB node_modules tree. See deploy/Dockerfile.frontend.
  output: "standalone",

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

  // Do not advertise the framework version to scanners.
  poweredByHeader: false,

  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
