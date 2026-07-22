/* Activity page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { ActivitySection } from "@/components/sections/ActivitySection";

export default function ActivityPage() {
  return (
    <div className="main-scroll">
      <ActivitySection />
    </div>
  );
}
