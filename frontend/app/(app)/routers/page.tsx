import type { Metadata } from "next";
import Link from "next/link";

import { Empty, PageHead, TableRegion } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { brand, int } from "@/lib/format";
import { one } from "@/lib/params";
import type { LeaseRow, VendorCount } from "@/lib/types";

export const metadata: Metadata = { title: "Routers LAN" };

export default async function RoutersPage({
  searchParams,
}: PageProps<"/routers">) {
  const q = one(await searchParams, "q");
  const [rows, vendors] = await Promise.all([
    apiFetch<LeaseRow[]>("/api/leases", { query: { q, limit: 500 } }),
    apiFetch<VendorCount[]>("/api/leases/vendors"),
  ]);
  // Facetas por marca: suma los fabricantes IEEE que son la misma marca (Huawei Technologies + Huawei Device).
  const brands = new Map<string, number>();
  for (const v of vendors) {
    const b =
      v.vendor === "(desconocido)"
        ? "Desconocido"
        : (brand(v.vendor) ?? v.vendor);
    brands.set(b, (brands.get(b) ?? 0) + v.leases);
  }
  const facets = [...brands].sort((a, b) => b[1] - a[1]).slice(0, 10);

  return (
    <>
      <PageHead
        title="Routers LAN"
        count={`${int(rows.length)}${rows.length === 500 ? "+" : ""} dispositivos`}
      />
      <form
        method="get"
        role="search"
        aria-label="Buscar routers"
        className="mb-3 flex flex-wrap items-end gap-2"
      >
        <div className="field min-w-[240px] flex-1">
          <label htmlFor="r-q">Buscar</label>
          <input
            id="r-q"
            name="q"
            type="search"
            defaultValue={q}
            className="input"
            placeholder="huawei 192.168.18. · hostname, fabricante, MAC o IP del router, nombre/IP del CPE, AP"
            spellCheck={false}
            enterKeyHint="search"
          />
        </div>
        <button type="submit" className="btn btn-primary">
          Buscar
        </button>
        {q ? (
          <Link href="/routers" className="btn btn-ghost">
            Limpiar
          </Link>
        ) : null}
      </form>
      <div className="mb-3 flex flex-wrap gap-2" aria-label="Marcas">
        {facets.map(([b, n]) => (
          <Link
            key={b}
            href={`/routers?q=${encodeURIComponent(b === "Desconocido" ? "" : b)}`}
            className="chip"
            data-on={q?.toLowerCase() === b.toLowerCase()}
          >
            {b} <b className="num">{n}</b>
          </Link>
        ))}
      </div>
      {rows.length ? (
        <TableRegion label="Routers LAN">
          <table className="data">
            <thead>
              <tr>
                <th scope="col">Hostname</th>
                <th scope="col">Fabricante</th>
                <th scope="col">IP LAN</th>
                <th scope="col">MAC</th>
                <th scope="col">CPE</th>
                <th scope="col">IP CPE</th>
                <th scope="col">AP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.cpe_mac + r.mac}>
                  <th scope="row">
                    {r.hostname ?? (
                      <span className="text-faint">sin hostname</span>
                    )}
                  </th>
                  <td title={r.vendor ?? undefined}>
                    {brand(r.vendor) ?? <span className="text-faint">-</span>}
                  </td>
                  <td className="num">{r.ip}</td>
                  <td className="num text-muted">{r.mac}</td>
                  <td>
                    <Link href={`/equipos/${r.cpe_mac}`} className="row-link">
                      {r.cpe_name ?? r.cpe_mac}
                    </Link>
                  </td>
                  <td className="num">{r.cpe_ip ?? "-"}</td>
                  <td>
                    {r.ap_name ?? (
                      <span
                        className="text-warn"
                        title="Su AP no esta en ninguna subnet escaneada"
                      >
                        sin AP
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableRegion>
      ) : (
        <div className="panel">
          <Empty>
            {q
              ? "Ningun router coincide. Todas las palabras tienen que aparecer."
              : "Sin leases todavia."}
          </Empty>
        </div>
      )}
    </>
  );
}
