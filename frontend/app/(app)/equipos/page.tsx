import type { Metadata } from "next";
import Link from "next/link";

import { SignalMeter } from "@/components/signal-meter";
import {
  Empty,
  hrefWith,
  PageHead,
  Pager,
  SortTh,
  TableRegion,
  When,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { brand, int } from "@/lib/format";
import { intParam, MAC_RE, one, oneOf, type SP } from "@/lib/params";
import { SIGNAL_CRIT, signalLevel } from "@/lib/signal";
import type { DevicePage } from "@/lib/types";

export const metadata: Metadata = { title: "Equipos" };

const LIMIT = 100;
const SORTS = [
  "name",
  "signal",
  "ip",
  "role",
  "platform",
  "last_seen",
  "ap",
  "lan",
] as const;

function readFilters(sp: SP) {
  const ap = one(sp, "ap");
  return {
    q: one(sp, "q"),
    role: oneOf(sp, "role", ["ap", "cpe", "unknown"] as const),
    ap: ap && MAC_RE.test(ap) ? ap : undefined,
    platform: one(sp, "platform"),
    lan: one(sp, "lan"),
    source: oneOf(sp, "source", ["ssh", "wstalist"] as const),
    signal_max: intParam(sp, "signal_max", -120, 0)?.toString(),
    sort: oneOf(sp, "sort", SORTS),
    order: oneOf(sp, "order", ["asc", "desc"] as const),
    offset: intParam(sp, "offset", 0, 1_000_000)?.toString(),
  };
}

export default async function EquiposPage({
  searchParams,
}: PageProps<"/equipos">) {
  const f = readFilters(await searchParams);
  let page: DevicePage | null = null;
  let error: string | null = null;
  try {
    page = await apiFetch<DevicePage>("/api/devices", {
      query: { ...f, limit: LIMIT },
    });
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    error = e.message;
  }

  const critHref = hrefWith("/equipos", f, {
    signal_max: String(SIGNAL_CRIT - 1),
    sort: "signal",
    order: "asc",
    offset: undefined,
  });
  const critOn = f.signal_max === String(SIGNAL_CRIT - 1);
  const active = Object.entries(f).some(
    ([k, v]) => v && !["sort", "order", "offset"].includes(k),
  );

  return (
    <>
      <PageHead
        title="Equipos"
        count={page ? `${int(page.total)} equipos` : undefined}
      />

      <form
        method="get"
        action="/equipos"
        role="search"
        aria-label="Filtrar equipos"
        className="mb-3 flex flex-wrap items-end gap-2"
      >
        <div className="field min-w-[220px] flex-1 basis-[260px]">
          <label htmlFor="f-q">Buscar</label>
          <input
            id="f-q"
            name="q"
            type="search"
            defaultValue={f.q}
            className="input"
            placeholder="nombre, MAC, IP, modelo, AP..."
            spellCheck={false}
            enterKeyHint="search"
          />
        </div>
        <div className="field">
          <label htmlFor="f-role">Rol</label>
          <select
            id="f-role"
            name="role"
            defaultValue={f.role ?? ""}
            className="select"
          >
            <option value="">Todos</option>
            <option value="cpe">CPE</option>
            <option value="ap">AP</option>
            <option value="unknown">Sin clasificar</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-signal">Senal hasta</label>
          <select
            id="f-signal"
            name="signal_max"
            defaultValue={f.signal_max ?? ""}
            className="select"
          >
            <option value="">Cualquiera</option>
            <option value="-65">-65 dBm</option>
            <option value="-70">-70 dBm</option>
            <option value={String(SIGNAL_CRIT - 1)}>
              {SIGNAL_CRIT - 1} dBm (critica)
            </option>
            <option value="-80">-80 dBm</option>
          </select>
        </div>
        <div className="field basis-[180px]">
          <label htmlFor="f-lan">Router LAN</label>
          <input
            id="f-lan"
            name="lan"
            defaultValue={f.lan}
            className="input"
            placeholder="huawei, HG8145..."
            spellCheck={false}
          />
        </div>
        <div className="field basis-[160px]">
          <label htmlFor="f-platform">Modelo antena</label>
          <input
            id="f-platform"
            name="platform"
            defaultValue={f.platform}
            className="input"
            placeholder="LiteBeam..."
            spellCheck={false}
          />
        </div>
        {f.ap ? <input type="hidden" name="ap" value={f.ap} /> : null}
        {f.sort ? <input type="hidden" name="sort" value={f.sort} /> : null}
        {f.order ? <input type="hidden" name="order" value={f.order} /> : null}
        <button type="submit" className="btn btn-primary">
          Filtrar
        </button>
        {active ? (
          <Link href="/equipos" className="btn btn-ghost">
            Limpiar
          </Link>
        ) : null}
      </form>

      <div className="mb-3 flex flex-wrap gap-2">
        <Link href={critHref} className="chip" data-on={critOn}>
          Senal <b>critica</b>
        </Link>
        <Link
          href={hrefWith("/equipos", f, {
            role: f.role === "cpe" ? undefined : "cpe",
            offset: undefined,
          })}
          className="chip"
          data-on={f.role === "cpe"}
        >
          Solo <b>CPE</b>
        </Link>
        <Link
          href={hrefWith("/equipos", f, {
            source: f.source === "wstalist" ? undefined : "wstalist",
            offset: undefined,
          })}
          className="chip"
          data-on={f.source === "wstalist"}
          title="Vistos desde su AP pero sin acceso SSH (credenciales o firewall)"
        >
          Sin <b>SSH</b>
        </Link>
        {f.ap ? (
          <Link
            href={hrefWith("/equipos", f, { ap: undefined })}
            className="chip"
            data-on="true"
          >
            AP <b className="num">{f.ap}</b> <span aria-hidden="true">x</span>
            <span className="visually-hidden">quitar filtro</span>
          </Link>
        ) : null}
      </div>

      {error ? (
        <p className="alert" data-tone="crit" role="alert">
          {error}
        </p>
      ) : page && page.items.length ? (
        <>
          <TableRegion label="Equipos">
            <table className="data">
              <thead>
                <tr>
                  <SortTh
                    label="Nombre"
                    field="name"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                  <SortTh
                    label="IP"
                    field="ip"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                  {f.role ? null : (
                    <SortTh
                      label="Rol"
                      field="role"
                      base="/equipos"
                      params={f}
                      defaultField="name"
                    />
                  )}
                  <SortTh
                    label="Modelo"
                    field="platform"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                  <SortTh
                    label="AP"
                    field="ap"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                  <SortTh
                    label="Senal"
                    field="signal"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                  <SortTh
                    label="Router LAN"
                    field="lan"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                  <SortTh
                    label="Visto"
                    field="last_seen"
                    base="/equipos"
                    params={f}
                    defaultField="name"
                  />
                </tr>
              </thead>
              <tbody>
                {page.items.map((d) => {
                  const hosts = d.lan_hosts ?? [];
                  const vendor = d.lan_vendors?.[0];
                  return (
                    <tr key={d.mac} data-level={signalLevel(d.signal)}>
                      <th scope="row">
                        <Link
                          href={`/equipos/${d.mac}`}
                          className="row-link"
                          title={d.mac}
                        >
                          {d.name ?? (
                            <span className="num text-muted">{d.mac}</span>
                          )}
                        </Link>
                      </th>
                      <td className="num">{d.ip ?? "-"}</td>
                      {f.role ? null : (
                        <td className="num text-muted uppercase">{d.role}</td>
                      )}
                      <td title={d.firmware ?? undefined}>
                        {d.platform ?? "-"}
                      </td>
                      <td>
                        {d.ap_mac ? (
                          <Link
                            href={`/equipos/${d.ap_mac}`}
                            className="row-link"
                          >
                            {d.ap_name ?? d.ap_mac}
                          </Link>
                        ) : (
                          <span className="text-faint">-</span>
                        )}
                      </td>
                      <td>
                        <SignalMeter dbm={d.signal} />
                      </td>
                      <td title={(d.lan_vendors ?? []).join(", ") || undefined}>
                        {hosts.length === 0 ? (
                          <span className="text-faint">-</span>
                        ) : hosts.length === 1 ? (
                          <>
                            {hosts[0]}
                            {vendor ? (
                              <span className="ml-1.5 text-[12px] text-faint">
                                {brand(vendor)}
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <>
                            {hosts[0]}
                            <span className="ml-1.5 text-[12px] text-faint">
                              +{hosts.length - 1}
                            </span>
                          </>
                        )}
                      </td>
                      <td>
                        <When iso={d.last_seen} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableRegion>
          <Pager
            base="/equipos"
            params={f}
            total={page.total}
            limit={LIMIT}
            offset={Number(f.offset ?? 0)}
          />
        </>
      ) : (
        <div className="panel">
          <Empty>
            {active
              ? "Ningun equipo coincide con estos filtros."
              : "Todavia no hay equipos. Agrega una subnet y lanza un escaneo."}
          </Empty>
        </div>
      )}
    </>
  );
}
