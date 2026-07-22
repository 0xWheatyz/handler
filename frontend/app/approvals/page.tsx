/* Approvals page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { ApprovalsSection } from "@/components/sections/ApprovalsSection";

export default function ApprovalsPage() {
  return (
    <div className="main-scroll">
      <ApprovalsSection />
    </div>
  );
}
