/* Agents page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { AgentsSection } from "@/components/sections/AgentsSection";

export default function AgentsPage() {
  return (
    <div className="main-scroll">
      <AgentsSection />
    </div>
  );
}
