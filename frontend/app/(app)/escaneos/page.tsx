import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm } from "@/components/action-form";
import { AutoRefresh, SubmitButton } from "@/components/client";
import { SortableTable } from "@/components/sortable-table";
import {
  Empty,
  PageHead,
  SCAN_LABEL,
  ScanState,
  TableRegion,
  When,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { getMe } from "@/lib/session";
import { ipKey, timeKey } from "@/lib/sort";
import type { Scan, Subnet } from "@/lib/types";

import { requestScan } from "../actions";

export const metadata: Metadata = { title: "Escaneos" };

function seconds(s: Scan): number | null {
  const start = timeKey(s.started_at);
  const end = timeKey(s.finished_at);
  return start === null || end === null ? null : (end - start) / 1000;
}

function duration(s: Scan): string {
  const secs = seconds(s);
  if (secs === null) return "-";
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
          <SortableTable
            columns={[
              "#",
              "Subnet",
              "Estado",
              "Origen",
              "Equipos",
              "OK",
              "Fallos",
              "Duracion",
              "Pedido",
            ]}
            initial={{ col: 0, dir: "desc" }}
            rows={scans.map((s) => ({
              id: s.id,
              level:
                s.status === "failed" || (s.hosts_failed ?? 0) > 0
                  ? "crit"
                  : undefined,
              sort: [
                s.id,
                ipKey(s.cidr),
                SCAN_LABEL[s.status],
                TRIGGER[s.trigger ?? ""] ?? s.trigger,
                s.hosts_alive,
                s.hosts_ok,
                s.hosts_failed,
                seconds(s),
                timeKey(s.requested_at),
              ],
              cells: (
                <>
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
                </>
              ),
            }))}
          />
        </TableRegion>
      ) : (
        <div className="panel">
          <Empty>Todavia no hubo escaneos.</Empty>
        </div>
      )}
    </>
  );
}
