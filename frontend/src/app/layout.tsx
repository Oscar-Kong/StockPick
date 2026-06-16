// Root Next.js layout that applies fonts, navigation, and API health status.
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ApiStatus } from "@/components/ApiStatus";
import { Nav } from "@/components/Nav";
import { Providers } from "@/components/Providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Picker Quant",
  description: "Daily portfolio decisions and penny stock screening for US equities",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body
        suppressHydrationWarning
        className="font-sans flex min-h-dvh flex-col text-base text-zinc-100"
      >
        <Providers>
          <Nav />
          <main className="app-main mx-auto flex w-full min-h-0 max-w-[1920px] flex-1 flex-col">
            {children}
          </main>
          <footer className="app-footer">
            <ApiStatus />
          </footer>
        </Providers>
      </body>
    </html>
  );
}
