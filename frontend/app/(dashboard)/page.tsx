import { redirect } from "next/navigation";

/**
 * Dashboard root: redirect to Analytics.
 * Server redirect avoids client-reference-manifest and ENOENT on Vercel build.
 */
export default function DashboardRootPage() {
  redirect("/analytics");
}
