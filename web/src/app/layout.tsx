import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Decision Flow",
  description: "Build, test and run decision flows",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {children}
        {/* top center: bottom right covers the settings panel; the offset clears the editor bar */}
        <Toaster position="top-center" offset={64} />
      </body>
    </html>
  );
}
