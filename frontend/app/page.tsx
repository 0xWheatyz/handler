/* Runs — the inbox and the app's landing page (root route). Rendered inside the shared
 * shell from the root layout; unlike the scrollable sections it owns its own split layout,
 * so it renders directly into main with no outer scroll wrapper. */
"use client";

import { RunsSection } from "@/components/sections/RunsSection";

export default function RunsPage() {
  return <RunsSection />;
}
