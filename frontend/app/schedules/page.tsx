/* Schedules page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { SchedulesSection } from "@/components/sections/SchedulesSection";

export default function SchedulesPage() {
  return (
    <div className="main-scroll">
      <SchedulesSection />
    </div>
  );
}
