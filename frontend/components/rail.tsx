"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { Role } from "@/lib/types";

import {
  IconAp,
  IconAudit,
  IconDevices,
  IconRouter,
  IconScan,
  IconSubnet,
  IconUsers,
} from "./icons";

const ITEMS = [
  { href: "/equipos", label: "Equipos", icon: IconDevices },
  { href: "/aps", label: "APs", icon: IconAp },
  { href: "/routers", label: "Routers LAN", icon: IconRouter },
  { href: "/escaneos", label: "Escaneos", icon: IconScan },
  { href: "/subnets", label: "Subnets", icon: IconSubnet },
] as const;

const ADMIN_ITEMS = [
  { href: "/usuarios", label: "Usuarios", icon: IconUsers },
  { href: "/auditoria", label: "Auditoria", icon: IconAudit },
] as const;

function RailLink({
  href,
  label,
  icon: Icon,
}: {
  href: string;
  label: string;
  icon: () => React.ReactNode;
}) {
  const pathname = usePathname();
  const current = pathname === href || pathname.startsWith(href + "/");
  return (
    <li>
      <Link
        href={href}
        title={label}
        aria-current={current ? "page" : undefined}
        className="grid size-9 place-items-center rounded-md text-faint transition-colors duration-150 hover:bg-raised hover:text-text aria-[current=page]:bg-raised aria-[current=page]:text-text aria-[current=page]:shadow-[inset_2px_0_0_var(--accent)]"
      >
        <Icon />
        <span className="visually-hidden">{label}</span>
      </Link>
    </li>
  );
}

export function Rail({ role }: { role: Role }) {
  return (
    <nav
      aria-label="Secciones"
      className="sticky top-0 flex h-dvh w-[52px] shrink-0 flex-col items-center border-r border-border bg-bg py-3"
    >
      <Link
        href="/equipos"
        className="mb-3 grid size-7 place-items-center rounded-sm border-[1.5px] border-text font-mono text-[11px] font-semibold text-text no-underline"
        title="CPE Scanner"
      >
        CS
      </Link>
      <ul className="flex flex-col gap-1">
        {ITEMS.map((i) => (
          <RailLink key={i.href} {...i} />
        ))}
      </ul>
      {role === "admin" ? (
        <ul className="mt-auto flex flex-col gap-1">
          {ADMIN_ITEMS.map((i) => (
            <RailLink key={i.href} {...i} />
          ))}
        </ul>
      ) : null}
    </nav>
  );
}
