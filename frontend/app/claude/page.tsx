/* Claude management page. The shell (sidebar, banners, store) comes from the root
 * layout; this route contributes only its section, in the shared scroll frame. */
"use client";

import { ClaudeSection } from "@/components/sections/ClaudeSection";

export default function ClaudePage() {
  return (
    <div className="main-scroll">
      <ClaudeSection />
    </div>
  );
}
