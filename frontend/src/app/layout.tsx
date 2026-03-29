import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Lazada Sniper — Mission Control",
  description: "High-concurrency bot dashboard for Lazada operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-[#0A0A0A] text-neutral-200 selection:bg-cyan-900 selection:text-white`}>
        {children}
      </body>
    </html>
  );
}
