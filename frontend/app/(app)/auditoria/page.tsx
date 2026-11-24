import type { Metadata } from "next";

import { SortableTable } from "@/components/sortable-table";
import { Empty, PageHead, TableRegion } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { requireAdmin } from "@/lib/session";
import { ipKey, timeKey } from "@/lib/sort";
import type { AuditEntry } from "@/lib/types";

export const metadata: Metadata = { title: "Auditoria" };

const ACTION: Record<string, string> = {
  login: "entro",
  logout: "salio",
  login_failed: "login fallido",
  login_throttled: "login bloqueado (demasiados intentos)",
  password_change: "cambio su clave",
  subnet_add: "agrego subnet",
  subnet_update: "modifico subnet",
  scan_request: "pidio escaneo",
  user_add: "creo usuario",
  user_update: "modifico usuario",
  hostkey_forget: "acepto host key nueva",
};

const ALERT = new Set(["login_failed", "login_throttled"]);

export default async function AuditoriaPage() {
  await requireAdmin();
  const entries = await apiFetch<AuditEntry[]>("/api/audit", {
    query: { limit: 300 },
  });

  return (
    <>
      <PageHead title="Auditoria" count={`ultimos ${entries.length} eventos`} />
      {entries.length ? (
        <TableRegion label="Auditoria">
          <SortableTable
            columns={["Fecha", "Quien", "Accion", "Detalle", "IP"]}
            initial={{ col: 0, dir: "desc" }}
            rows={entries.map((e) => ({
              id: e.id,
              level: ALERT.has(e.action) ? "crit" : undefined,
              sort: [
                timeKey(e.at),
                e.actor,
                ACTION[e.action] ?? e.action,
                e.detail ? JSON.stringify(e.detail) : null,
                ipKey(e.ip),
              ],
              cells: (
                <>
                  <td className="num">{dateTime(e.at)}</td>
                  <th scope="row">{e.actor}</th>
                  <td className={ALERT.has(e.action) ? "text-crit" : ""}>
                    {ACTION[e.action] ?? e.action}
                  </td>
                  <td
                    className="num max-w-[420px] text-muted"
                    title={e.detail ? JSON.stringify(e.detail) : undefined}
                  >
                    {e.detail ? JSON.stringify(e.detail) : "-"}
                  </td>
                  <td className="num">{e.ip ?? "-"}</td>
                </>
              ),
            }))}
          />
        </TableRegion>
      ) : (
        <div className="panel">
          <Empty>Sin eventos.</Empty>
        </div>
      )}
    </>
  );
}
