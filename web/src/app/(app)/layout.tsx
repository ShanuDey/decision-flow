import Link from "next/link";

import { requireSession } from "@/lib/auth/session";

import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireSession();
  return (
    <div className="flex min-h-screen flex-1">
      <aside className="hidden w-[232px] shrink-0 flex-col gap-6 border-r bg-muted/40 p-4 md:flex">
        <Link href="/flows" className="px-3 pt-2 text-base font-semibold tracking-tight">
          Decision Flow
        </Link>
        <SidebarNav />
        <div className="mt-auto">
          <UserMenu name={user.name} email={user.email} />
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-8">{children}</main>
    </div>
  );
}
