/* Users page (admin only — the sidebar hides it otherwise; the API enforces it). */
"use client";

import { UsersSection } from "@/components/sections/UsersSection";

export default function UsersPage() {
  return (
    <div className="main-scroll">
      <UsersSection />
    </div>
  );
}
