import type { Metadata } from "next";
import Link from "next/link";

import { Empty, hrefWith, PageHead, TableRegion } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { brand, int } from "@/lib/format";
import { intParam, one } from "@/lib/params";
import type { LeaseRow, VendorCount } from "@/lib/types";

export const metadata: Metadata = { title: "Routers LAN" };

const LIMIT = 200;

export default async function RoutersPage({
  searchParams,
}: PageProps<"/routers">) {
  const sp = await searchParams;
  const q = one(sp, "q");
  const offset = intParam(sp, "offset", 0, 1_000_000) ?? 0;
  const [page, vendors] = await Promise.all([
    // Uno de mas: si vuelve, hay pagina siguiente (la API no cuenta el total de leases).
    apiFetch<LeaseRow[]>("/api/leases", {
      query: { q, limit: LIMIT + 1, offset },
    }),
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
  const hasNext = page.length > LIMIT;
  const rows = page.slice(0, LIMIT);
  const params = { q };

  return (
    <>
      <PageHead
        title="Routers LAN"
        count={
          rows.length
            ? `${int(offset + 1)}-${int(offset + rows.length)}${hasNext ? " de mas" : ` de ${int(offset + rows.length)}`}`
            : undefined
        }
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
      ) : null}
      {rows.length && (offset > 0 || hasNext) ? (
        <nav
          aria-label="Paginas"
          className="mt-3 flex items-center justify-end gap-2 text-[13px] text-muted"
        >
          <span className="num">
            {offset + 1}-{offset + rows.length}
          </span>
          {offset > 0 ? (
            <Link
              className="btn btn-sm"
              href={hrefWith("/routers", params, {
                offset: offset > LIMIT ? String(offset - LIMIT) : undefined,
              })}
            >
              Anterior
            </Link>
          ) : null}
          {hasNext ? (
            <Link
              className="btn btn-sm"
              href={hrefWith("/routers", params, {
                offset: String(offset + LIMIT),
              })}
            >
              Siguiente
            </Link>
          ) : null}
        </nav>
      ) : null}
      {rows.length ? null : (
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
