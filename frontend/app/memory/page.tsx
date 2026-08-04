/* Memory page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { MemorySection } from "@/components/sections/MemorySection";

export default function MemoryPage() {
  return (
    <div className="main-scroll">
      <MemorySection />
    </div>
  );
}
