import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm } from "@/components/action-form";
import { AutoRefresh, SubmitButton } from "@/components/client";
import { Empty, PageHead, ScanState, TableRegion, When } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { getMe } from "@/lib/session";
import type { Scan, Subnet } from "@/lib/types";

import { requestScan } from "../actions";

export const metadata: Metadata = { title: "Escaneos" };

function duration(s: Scan): string {
  if (!s.started_at || !s.finished_at) return "-";
  const secs =
    (new Date(s.finished_at).getTime() - new Date(s.started_at).getTime()) /
    1000;
  return secs < 60 ? `${secs.toFixed(1)} s` : `${Math.round(secs / 60)} min`;
}

const TRIGGER: Record<string, string> = {
  manual: "manual",
  schedule: "programado",
  cli: "consola",
};

export default async function EscaneosPage() {
  const [me, scans, subnets] = await Promise.all([
    getMe(),
    apiFetch<Scan[]>("/api/scans", { query: { limit: 50 } }),
    apiFetch<Subnet[]>("/api/subnets"),
  ]);
  const busy = scans.some(
    (s) => s.status === "pending" || s.status === "running",
  );

  return (
    <>
      <AutoRefresh active={busy} />
      <PageHead
        title="Escaneos"
        count={busy ? "hay escaneos en curso" : undefined}
      />

      {me.role === "admin" ? (
        <ActionForm
          action={requestScan}
          className="mb-4 flex flex-wrap items-end gap-2"
          resetOnSuccess={false}
        >
          <div className="field">
            <label htmlFor="scan-subnet">Subnet</label>
            <select
              id="scan-subnet"
              name="subnet_id"
              className="select"
              defaultValue=""
            >
              <option value="">Todas las habilitadas</option>
              {subnets
                .filter((s) => s.enabled)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.cidr}
                    {s.name ? ` · ${s.name}` : ""}
                  </option>
                ))}
            </select>
          </div>
          <SubmitButton className="btn btn-primary" pendingText="Encolando...">
            Escanear ahora
          </SubmitButton>
        </ActionForm>
      ) : null}

      {scans.length ? (
        <TableRegion label="Escaneos">
          <table className="data">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Subnet</th>
                <th scope="col">Estado</th>
                <th scope="col">Origen</th>
                <th scope="col">Equipos</th>
                <th scope="col">OK</th>
                <th scope="col">Fallos</th>
                <th scope="col">Duracion</th>
                <th scope="col">Pedido</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => (
                <tr
                  key={s.id}
                  data-level={
                    s.status === "failed" || (s.hosts_failed ?? 0) > 0
                      ? "crit"
                      : undefined
                  }
                >
                  <th scope="row">
                    <Link href={`/escaneos/${s.id}`} className="row-link num">
                      {s.id}
                    </Link>
                  </th>
                  <td>
                    <span className="num">{s.cidr ?? "-"}</span>
                    {s.subnet_name ? (
                      <span className="ml-2 text-muted">{s.subnet_name}</span>
                    ) : null}
                  </td>
                  <td>
                    <ScanState status={s.status} />
                  </td>
                  <td className="text-muted">
                    {TRIGGER[s.trigger ?? ""] ?? s.trigger ?? "-"}
                  </td>
                  <td className="num">{s.hosts_alive ?? "-"}</td>
                  <td className="num">{s.hosts_ok ?? "-"}</td>
                  <td
                    className={`num ${(s.hosts_failed ?? 0) > 0 ? "text-crit" : ""}`}
                  >
                    {s.hosts_failed ?? "-"}
                  </td>
                  <td className="num">{duration(s)}</td>
                  <td>
                    <When iso={s.requested_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableRegion>
      ) : (
        <div className="panel">
          <Empty>Todavia no hubo escaneos.</Empty>
        </div>
      )}
    </>
  );
}
