import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Debug Dojo — Python Coding Practice",
  description:
    "Master Python with AI-powered explanations, progressive hints, and concept mastery tracking.",
  keywords: ["python", "coding", "practice", "AI", "EdTech"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} antialiased`}>{children}</body>
    </html>
  );
}
