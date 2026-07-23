/* The old Claude Login route. The login flow now lives on the Claude management page
 * (/claude, Account tab); this stub only redirects old bookmarks there. */
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LoginRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/claude");
  }, [router]);
  return null;
}
