import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Debug Dojo [26] — Forensic Python Practice",
  description:
    "DI-01 Hackathon: Master Python debugging with sandboxed execution, AI diagnostic explanations, and progressive hints.",
  keywords: ["python", "debugging", "dojo", "MXESA", "edtech", "hackathon"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body
        className={`${inter.variable} ${mono.variable} font-sans bg-[#141414] text-[#F0EFEA] antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
