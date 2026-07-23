import type { Metadata } from "next";
import "./globals.css";
import { AppFrame } from "@/components/AppFrame";

export const metadata: Metadata = {
  title: "Handler · Claude Activity",
  description: "Monitor and manage Claude Code agents across projects.",
};

/* The frame (token gate, store/polling, sidebar) wraps every route and persists across
 * navigation; each page under app/ supplies only its own section content. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppFrame>{children}</AppFrame>
      </body>
    </html>
  );
}
