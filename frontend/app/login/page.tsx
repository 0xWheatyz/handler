/* Claude Login page. The shell (sidebar, banners, store) comes from the root layout; this
 * route contributes only its section, in the shared scroll frame. */
"use client";

import { LoginSection } from "@/components/sections/LoginSection";

export default function LoginPage() {
  return (
    <div className="main-scroll">
      <LoginSection />
    </div>
  );
}
