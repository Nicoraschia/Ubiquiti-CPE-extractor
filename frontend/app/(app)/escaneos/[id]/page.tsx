import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AutoRefresh } from "@/components/client";
import { Empty, ScanState, TableRegion } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { ScanDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Escaneo" };

export default async function ScanPage({
  params,
}: PageProps<"/escaneos/[id]">) {
  const { id } = await params;
  if (!/^\d{1,9}$/.test(id)) notFound();
  let scan: ScanDetail;
  try {
    scan = await apiFetch<ScanDetail>(`/api/scans/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const busy = scan.status === "pending" || scan.status === "running";

  return (
    <article className="flex flex-col gap-4">
      <AutoRefresh active={busy} />
      <header>
        <Link href="/escaneos" className="link text-[13px]">
          Escaneos
        </Link>
        <h1 className="mt-1 font-cond text-[24px] font-semibold">
          Escaneo <span className="num text-[22px]">#{scan.id}</span> ·{" "}
          <span className="num text-[22px]">{scan.cidr ?? "-"}</span>
        </h1>
        <p className="mt-1 flex flex-wrap items-center gap-3 text-[13px] text-muted">
          <ScanState status={scan.status} />
          <span>pedido {dateTime(scan.requested_at)}</span>
          {scan.finished_at ? (
            <span>termino {dateTime(scan.finished_at)}</span>
          ) : null}
          <span className="num">
            {scan.hosts_alive ?? "-"} equipos · {scan.hosts_ok ?? "-"} ok ·{" "}
            {scan.hosts_failed ?? "-"} fallos
          </span>
        </p>
      </header>
      {scan.error ? (
        <p className="alert" data-tone="crit" role="alert">
          {scan.error}
        </p>
      ) : null}
      <section aria-labelledby="err-title">
        <h2 id="err-title" className="label-caps mb-2">
          Equipos con error
        </h2>
        {scan.errors.length ? (
          <TableRegion label="Errores del escaneo">
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Host</th>
                  <th scope="col">Error</th>
                </tr>
              </thead>
              <tbody>
                {scan.errors.map((e) => (
                  <tr key={e.host} data-level="crit">
                    <th scope="row" className="num">
                      {e.host}
                    </th>
                    <td className="max-w-none whitespace-normal text-muted">
                      {e.error}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableRegion>
        ) : (
          <div className="panel">
            <Empty>{busy ? "Escaneando..." : "Sin errores."}</Empty>
          </div>
        )}
      </section>
    </article>
  );
}
