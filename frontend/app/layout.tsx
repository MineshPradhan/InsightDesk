import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "InsightDesk — support triage console",
  description:
    "Every ticket routed, prioritised and answered from the knowledge base, with the evidence attached.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Nav />
        <main className="mx-auto max-w-[1440px] px-5 pb-16">{children}</main>
      </body>
    </html>
  );
}
