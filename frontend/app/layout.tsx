import type { Metadata, Viewport } from "next";
import {
  IBM_Plex_Mono,
  IBM_Plex_Sans,
  IBM_Plex_Sans_Condensed,
} from "next/font/google";
import { connection } from "next/server";

import "./globals.css";

// next/font descarga las fuentes en el build: el navegador no le pide nada a Google (CSP font-src 'self').
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
const plexCond = IBM_Plex_Sans_Condensed({
  variable: "--font-plex-cond",
  subsets: ["latin"],
  weight: ["500", "600"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: { default: "CPE Scanner", template: "%s · CPE Scanner" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // Todo se renderiza por request: el nonce del CSP no puede ir en HTML prerenderizado.
  await connection();
  return (
    <html
      lang="es-AR"
      className={`${plexSans.variable} ${plexCond.variable} ${plexMono.variable}`}
    >
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
