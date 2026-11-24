import type { Metadata } from "next";
import Link from "next/link";

import { SignalMeter } from "@/components/signal-meter";
import { SortableTable } from "@/components/sortable-table";
import { Empty, PageHead, TableRegion, When } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { signalLevel } from "@/lib/signal";
import { ipKey, timeKey } from "@/lib/sort";
import type { ApSummary } from "@/lib/types";

export const metadata: Metadata = { title: "APs" };

export default async function ApsPage() {
  const aps = await apiFetch<ApSummary[]>("/api/aps");

  return (
    <>
      <PageHead title="Access points" count={`${aps.length} AP`} />
      {aps.length ? (
        <TableRegion label="Access points">
          {/* De entrada, los AP con el peor CPE arriba: es donde hay que mirar primero. */}
          <SortableTable
            columns={[
              "AP",
              "IP",
              "Modelo",
              "SSID",
              "CPE",
              "Peor",
              "Promedio",
              "Visto",
            ]}
            initial={{ col: 5, dir: "asc" }}
            rows={aps.map((ap) => ({
              id: ap.mac,
              level: signalLevel(ap.worst_signal),
              sort: [
                ap.name ?? ap.mac,
                ipKey(ap.ip),
                ap.platform,
                ap.ssid,
                ap.stations,
                ap.worst_signal,
                ap.avg_signal,
                timeKey(ap.last_seen),
              ],
              cells: (
                <>
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
                </>
              ),
            }))}
          />
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
