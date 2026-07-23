/* Shared page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { SharedSection } from "@/components/sections/SharedSection";

export default function SharedPage() {
  return (
    <div className="main-scroll">
      <SharedSection />
    </div>
  );
}
