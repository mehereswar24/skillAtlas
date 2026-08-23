import type { Metadata } from "next";
import { headers } from "next/headers";
import { Outfit, Geist_Mono, Plus_Jakarta_Sans } from "next/font/google";

import { SmoothScroll } from "@/components/smooth-scroll";
import { ThemeScript } from "@/components/theme-toggle";
import "./globals.css";

// Outfit for headings (modern, geometric), Plus Jakarta Sans for UI.
const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "SkillAtlas — chart a path to any skill",
    template: "%s · SkillAtlas",
  },
  description:
    "Pick a career or skill and get a week-by-week route built from a real prerequisite graph, with curated resources, quizzes and a tutor that knows your progress.",
};

import { MagneticCursor } from "@/components/ui/magnetic-cursor";

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // The nonce `src/proxy.ts` minted for this request. Reading a header here
  // also opts the whole app into dynamic rendering, which nonce-based CSP
  // requires anyway: a page prerendered at build time has no request to take a
  // nonce from, so its inline scripts would be blocked at runtime.
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html
      lang="en"
      // suppressHydrationWarning: ThemeScript sets `class` and `style` on this
      // element before React hydrates, which is the whole point — it prevents
      // a flash of the wrong theme.
      suppressHydrationWarning
      className={`${outfit.variable} ${jakarta.variable} ${geistMono.variable} h-full`}
    >
      <head>
        <ThemeScript nonce={nonce} />
      </head>
      <body className="flex min-h-full flex-col">
        <SmoothScroll />
        <MagneticCursor
          magneticFactor={0.55}
          blendMode="exclusion"
          cursorSize={30}
        >
          {children}
        </MagneticCursor>
      </body>
    </html>
  );
}
