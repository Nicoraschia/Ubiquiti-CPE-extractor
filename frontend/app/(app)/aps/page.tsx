import type { Metadata } from "next";
import Link from "next/link";

import { SignalMeter } from "@/components/signal-meter";
import { Empty, PageHead, TableRegion, When } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { oneOf } from "@/lib/params";
import { signalLevel } from "@/lib/signal";
import type { ApSummary } from "@/lib/types";

export const metadata: Metadata = { title: "APs" };

export default async function ApsPage({ searchParams }: PageProps<"/aps">) {
  const sort =
    oneOf(await searchParams, "sort", ["name", "worst"] as const) ?? "worst";
  const aps = await apiFetch<ApSummary[]>("/api/aps");
  // Por defecto, los AP con el peor CPE arriba: es donde hay que mirar primero.
  if (sort === "worst")
    aps.sort((a, b) => (a.worst_signal ?? 0) - (b.worst_signal ?? 0));

  return (
    <>
      <PageHead title="Access points" count={`${aps.length} AP`}>
        <nav aria-label="Orden" className="flex gap-2">
          <Link
            href="/aps"
            className="chip"
            data-on={sort === "worst"}
            aria-current={sort === "worst" ? "true" : undefined}
          >
            Peor senal primero
          </Link>
          <Link
            href="/aps?sort=name"
            className="chip"
            data-on={sort === "name"}
            aria-current={sort === "name" ? "true" : undefined}
          >
            Por nombre
          </Link>
        </nav>
      </PageHead>
      {aps.length ? (
        <TableRegion label="Access points">
          <table className="data">
            <thead>
              <tr>
                <th
                  scope="col"
                  aria-sort={sort === "name" ? "ascending" : undefined}
                >
                  AP
                </th>
                <th scope="col">IP</th>
                <th scope="col">Modelo</th>
                <th scope="col">SSID</th>
                <th scope="col">CPE</th>
                <th
                  scope="col"
                  aria-sort={sort === "worst" ? "ascending" : undefined}
                >
                  Peor
                </th>
                <th scope="col">Promedio</th>
                <th scope="col">Visto</th>
              </tr>
            </thead>
            <tbody>
              {aps.map((ap) => (
                <tr key={ap.mac} data-level={signalLevel(ap.worst_signal)}>
                  <th scope="row">
                    <Link href={`/equipos/${ap.mac}`} className="row-link">
                      {ap.name ?? ap.mac}
                    </Link>
                  </th>
                  <td className="num">{ap.ip ?? "-"}</td>
                  <td title={ap.firmware ?? undefined}>{ap.platform ?? "-"}</td>
                  <td>{ap.ssid ?? "-"}</td>
                  <td className="num">
                    <Link
                      href={`/equipos?ap=${ap.mac}&sort=signal`}
                      className="row-link"
                    >
                      {ap.stations}
                    </Link>
                  </td>
                  <td>
                    <SignalMeter dbm={ap.worst_signal} />
                  </td>
                  <td>
                    <SignalMeter dbm={ap.avg_signal} bars={false} />
                  </td>
                  <td>
                    <When iso={ap.last_seen} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableRegion>
      ) : (
        <div className="panel">
          <Empty>
            No hay AP todavia. Los AP aparecen al escanear su subnet de gestion.
          </Empty>
        </div>
      )}
    </>
  );
}
