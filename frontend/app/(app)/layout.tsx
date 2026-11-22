import Link from "next/link";

import { CommandPalette } from "@/components/command-palette";
import { Rail } from "@/components/rail";
import { getMe } from "@/lib/session";

import { logout } from "../login/actions";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const me = await getMe();
  return (
    <div className="flex min-h-dvh">
      <Rail role={me.role} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-[52px] items-center gap-4 border-b border-border bg-bg/95 px-4 backdrop-blur-sm">
          <CommandPalette />
          <div className="ml-auto flex items-center gap-3 text-[13px] text-muted">
            <Link
              href="/cuenta"
              className="text-muted no-underline hover:text-text"
            >
              {me.username}
            </Link>
            <span className="rounded-sm border border-border-strong px-1.5 py-0.5 font-mono text-[11px]">
              {me.role}
            </span>
            <form action={logout}>
              <button type="submit" className="btn btn-ghost btn-sm">
                Salir
              </button>
            </form>
          </div>
        </header>
        <main className="flex-1 px-4 pb-10 pt-5 sm:px-5">{children}</main>
      </div>
    </div>
  );
}
