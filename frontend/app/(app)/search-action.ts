"use server";

import { z } from "zod";

import { apiFetch } from "@/lib/api";
import type { DevicePage, LeaseRow } from "@/lib/types";

export type SearchHit =
  | {
      kind: "device";
      mac: string;
      title: string;
      detail: string;
      signal: number | null;
    }
  | { kind: "lease"; mac: string; title: string; detail: string; signal: null };

const Query = z.string().trim().min(2).max(100);

/** Busqueda global de la paleta. Corre con la sesion del usuario: la API valida y filtra. */
export async function search(raw: string): Promise<SearchHit[]> {
  const q = Query.safeParse(raw);
  if (!q.success) return [];
  const [devices, leases] = await Promise.all([
    apiFetch<DevicePage>("/api/devices", {
      query: { q: q.data, limit: 8, sort: "name" },
    }),
    apiFetch<LeaseRow[]>("/api/leases", { query: { q: q.data, limit: 6 } }),
  ]);
  return [
    ...devices.items.map<SearchHit>((d) => ({
      kind: "device",
      mac: d.mac,
      title: d.name ?? d.mac,
      detail: [
        d.role.toUpperCase(),
        d.ip,
        d.platform,
        d.ap_name && `AP ${d.ap_name}`,
      ]
        .filter(Boolean)
        .join(" · "),
      signal: d.signal,
    })),
    ...leases.map<SearchHit>((l) => ({
      kind: "lease",
      mac: l.cpe_mac,
      title: l.hostname ?? l.mac,
      detail: [
        "Router LAN",
        l.ip,
        l.vendor,
        l.cpe_name && `detras de ${l.cpe_name}`,
      ]
        .filter(Boolean)
        .join(" · "),
      signal: null,
    })),
  ];
}
