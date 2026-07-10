import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Handler · Claude Activity",
  description: "Monitor and manage Claude Code agents across projects.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
