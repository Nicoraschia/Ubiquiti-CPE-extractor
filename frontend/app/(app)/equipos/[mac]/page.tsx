import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache, type ReactNode } from "react";

import { SignalMeter } from "@/components/signal-meter";
import { Sparkline } from "@/components/sparkline";
import { Empty, TableRegion, When } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { brand, dateTime, distance, plan, uptime } from "@/lib/format";
import { MAC_RE } from "@/lib/params";
import { signalLevel } from "@/lib/signal";
import type { DeviceDetail } from "@/lib/types";

// cache: metadata y pagina comparten una sola consulta a la API.
const load = cache(async (raw: string): Promise<DeviceDetail> => {
  const mac = decodeURIComponent(raw);
  if (!MAC_RE.test(mac)) notFound();
  try {
    return await apiFetch<DeviceDetail>(
      `/api/devices/${encodeURIComponent(mac)}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
});

export async function generateMetadata({
  params,
}: PageProps<"/equipos/[mac]">): Promise<Metadata> {
  const d = await load((await params).mac);
  return { title: d.name ?? d.mac };
}

function Stat({
  k,
  children,
  tone,
}: {
  k: string;
  children: ReactNode;
  tone?: string;
}) {
  return (
    <div className="border-r border-border px-4 py-3 last:border-r-0">
      <div className="label-caps">{k}</div>
      <div
        className={`mt-1 font-cond text-[22px] font-medium tabular-nums leading-tight ${tone ?? ""}`}
      >
        {children}
      </div>
    </div>
  );
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted">{k}</dt>
      <dd className="min-w-0">{children}</dd>
    </>
  );
}

export default async function DevicePage({
  params,
}: PageProps<"/equipos/[mac]">) {
  const d = await load((await params).mac);
  const history = [...d.link_history].reverse(); // la API lo da del mas nuevo al mas viejo
  const points = history
    .filter((h) => h.signal !== null)
    .map((h) => ({ at: h.seen_at, dbm: h.signal as number }));
  const last = d.link_history[0];
  const apChanges = history.filter(
    (h, i) => i > 0 && h.ap_mac !== history[i - 1].ap_mac,
  ).length;
  const crit = d.stations.filter(
    (s) => signalLevel(s.signal) === "crit",
  ).length;
  const signals = d.stations
    .map((s) => s.signal)
    .filter((s): s is number => s !== null);

  return (
    <article className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="label-caps mb-1">
            {d.role === "ap"
              ? "Access point"
              : d.role === "cpe"
                ? "CPE"
                : "Equipo"}
          </p>
          <h1 className="font-cond text-[28px] font-semibold leading-tight">
            {d.name ?? d.mac}
          </h1>
          <p className="num mt-1 text-muted">
            {d.mac} · {d.ip ?? "sin IP"} · {d.platform ?? "modelo desconocido"}{" "}
            · {d.firmware ?? "-"}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-3 text-[13px] text-muted">
          visto <When iso={d.last_seen} /> ·{" "}
          {d.source === "ssh" ? "leido por SSH" : "solo visto desde el AP"}
        </div>
      </header>

      {d.source === "wstalist" && d.role !== "ap" ? (
        <p className="alert" data-tone="warn">
          No se pudo entrar por SSH a este CPE: los datos vienen de su AP y no
          hay leases ni plan. Revisar credenciales o firewall.
        </p>
      ) : null}

      {d.role === "ap" ? (
        <section className="panel" aria-labelledby="st-title">
          <div className="grid grid-cols-2 border-b border-border sm:grid-cols-4">
            <Stat k="CPE">{d.stations.length}</Stat>
            <Stat
              k="Peor senal"
              tone={
                signals.length && signalLevel(Math.min(...signals)) === "crit"
                  ? "text-crit"
                  : ""
              }
            >
              {signals.length ? Math.min(...signals) : "-"}
              <small className="ml-1 font-mono text-[12px] text-muted">
                dBm
              </small>
            </Stat>
            <Stat k="Promedio">
              {signals.length
                ? Math.round(
                    signals.reduce((a, b) => a + b, 0) / signals.length,
                  )
                : "-"}
              <small className="ml-1 font-mono text-[12px] text-muted">
                dBm
              </small>
            </Stat>
            <Stat k="Criticos" tone={crit ? "text-crit" : ""}>
              {crit}
            </Stat>
          </div>
          <h2 id="st-title" className="visually-hidden">
            CPE conectados
          </h2>
          {d.stations.length ? (
            <div
              className="table-wrap"
              role="region"
              aria-label="CPE conectados"
              tabIndex={0}
            >
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">CPE</th>
                    <th scope="col" aria-sort="ascending">
                      Senal
                    </th>
                    <th scope="col">IP</th>
                    <th scope="col">Modelo</th>
                    <th scope="col">Visto</th>
                  </tr>
                </thead>
                <tbody>
                  {d.stations.map((s) => (
                    <tr key={s.mac} data-level={signalLevel(s.signal)}>
                      <th scope="row">
                        <Link href={`/equipos/${s.mac}`} className="row-link">
                          {s.name ?? s.mac}
                        </Link>
                      </th>
                      <td>
                        <SignalMeter dbm={s.signal} />
                      </td>
                      <td className="num">{s.ip ?? "-"}</td>
                      <td>{s.platform ?? "-"}</td>
                      <td>
                        <When iso={s.last_seen} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>Este AP no tenia CPE asociados en el ultimo escaneo.</Empty>
          )}
        </section>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <section className="panel p-4" aria-labelledby="sig-title">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 id="sig-title" className="label-caps">
                Senal, ultimos {points.length} escaneos
              </h2>
              <SignalMeter dbm={d.signal} />
            </div>
            <Sparkline points={points} />
            {apChanges ? (
              <p className="mt-3 text-[13px] text-warn">
                Cambio de AP {apChanges} {apChanges === 1 ? "vez" : "veces"} en
                este periodo.
              </p>
            ) : null}
          </section>

          <section className="panel p-4" aria-labelledby="link-title">
            <h2 id="link-title" className="label-caps mb-3">
              Enlace
            </h2>
            <dl className="grid grid-cols-[110px_1fr] gap-x-4 gap-y-2 text-[13px]">
              <Row k="AP">
                {d.ap_mac ? (
                  <Link href={`/equipos/${d.ap_mac}`} className="link">
                    {d.ap_name ?? d.ap_mac}
                  </Link>
                ) : (
                  <span className="text-warn">
                    desconocido: su AP no esta en ninguna subnet escaneada
                  </span>
                )}
                {d.ap_ip ? (
                  <span className="num ml-2 text-muted">{d.ap_ip}</span>
                ) : null}
              </Row>
              <Row k="SSID">{d.ssid ?? "-"}</Row>
              <Row k="Senal remota">
                <span className="num">{last?.remote_signal ?? "-"} dBm</span>
              </Row>
              <Row k="Ruido">
                <span className="num">{last?.noisefloor ?? "-"} dBm</span>
              </Row>
              <Row k="Linkscore">
                <span className="num">
                  {last
                    ? `${last.dl_linkscore ?? "-"} / ${last.ul_linkscore ?? "-"}`
                    : "-"}
                </span>
              </Row>
              <Row k="Distancia">
                <span className="num">{distance(last?.distance_m)}</span>
              </Row>
              <Row k="Uptime enlace">
                <span className="num">{uptime(last?.uptime_s)}</span>
              </Row>
              <Row k="Plan">
                <span className="num">{plan(d.shaper_in, d.shaper_out)}</span>
              </Row>
              <Row k="Modo red">{d.netmode ?? "-"}</Row>
            </dl>
          </section>
        </div>
      )}

      {d.role !== "ap" ? (
        <section aria-labelledby="lan-title">
          <h2 id="lan-title" className="label-caps mb-2">
            Dispositivos en la LAN del cliente
          </h2>
          {d.leases.length ? (
            <TableRegion label="Leases DHCP">
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Hostname</th>
                    <th scope="col">Fabricante</th>
                    <th scope="col">IP</th>
                    <th scope="col">MAC</th>
                    <th scope="col">Leido</th>
                  </tr>
                </thead>
                <tbody>
                  {d.leases.map((l) => (
                    <tr key={l.mac}>
                      <th scope="row">
                        {l.hostname ?? (
                          <span className="text-faint">sin hostname</span>
                        )}
                      </th>
                      <td title={l.vendor ?? undefined}>
                        {brand(l.vendor) ?? (
                          <span className="text-faint">-</span>
                        )}
                      </td>
                      <td className="num">{l.ip}</td>
                      <td className="num text-muted">{l.mac}</td>
                      <td>
                        <When iso={l.seen_at} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableRegion>
          ) : (
            <div className="panel">
              <Empty>Sin leases leidos de este CPE.</Empty>
            </div>
          )}
        </section>
      ) : null}

      {d.link_history.length ? (
        <details className="panel">
          <summary className="cursor-pointer px-4 py-3 label-caps">
            Historial de enlace ({d.link_history.length})
          </summary>
          <div
            className="table-wrap"
            role="region"
            aria-label="Historial de enlace"
            tabIndex={0}
          >
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">AP</th>
                  <th scope="col">Senal</th>
                  <th scope="col">Remota</th>
                  <th scope="col">Uptime</th>
                </tr>
              </thead>
              <tbody>
                {d.link_history.map((h) => (
                  <tr key={h.seen_at + h.ap_mac}>
                    <td className="num">{dateTime(h.seen_at)}</td>
                    <td className="num text-muted">{h.ap_mac}</td>
                    <td>
                      <SignalMeter dbm={h.signal} bars={false} />
                    </td>
                    <td className="num">{h.remote_signal ?? "-"}</td>
                    <td className="num">{uptime(h.uptime_s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </article>
  );
}
