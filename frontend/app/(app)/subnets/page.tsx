import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import { SubmitButton } from "@/components/client";
import { SortableTable } from "@/components/sortable-table";
import { Empty, PageHead, TableRegion, When } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { getMe } from "@/lib/session";
import { ipKey, timeKey } from "@/lib/sort";
import type { Subnet } from "@/lib/types";

import { addSubnet, setSubnetEnabled } from "../actions";

export const metadata: Metadata = { title: "Subnets" };

export default async function SubnetsPage() {
  const [me, subnets] = await Promise.all([
    getMe(),
    apiFetch<Subnet[]>("/api/subnets"),
  ]);
  const admin = me.role === "admin";

  return (
    <>
      <PageHead
        title="Subnets"
        count={`${subnets.filter((s) => s.enabled).length} habilitadas de ${subnets.length}`}
      />

      {admin ? (
        <ActionForm
          action={addSubnet}
          className="panel mb-4 flex flex-wrap items-end gap-3 p-4"
        >
          <div className="field">
            <label htmlFor="s-cidr">Subnet (CIDR)</label>
            <input
              id="s-cidr"
              name="cidr"
              className="input num w-[200px]"
              placeholder="192.168.18.0/24"
              required
              pattern="^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$"
              inputMode="decimal"
              spellCheck={false}
              autoComplete="off"
            />
            <span className="field-error">Formato: 192.168.18.0/24</span>
          </div>
          <div className="field flex-1 basis-[200px]">
            <label htmlFor="s-name">Nombre (opcional)</label>
            <input
              id="s-name"
              name="name"
              className="input"
              maxLength={80}
              placeholder="Gestion zona norte"
              autoComplete="off"
            />
          </div>
          <SubmitButton className="btn btn-primary" pendingText="Agregando...">
            Agregar subnet
          </SubmitButton>
        </ActionForm>
      ) : null}

      {subnets.length ? (
        <TableRegion label="Subnets">
          <SortableTable
            columns={[
              "Subnet",
              "Nombre",
              "Estado",
              "Alta",
              ...(admin ? [{ hidden: "Acciones" }] : []),
            ]}
            initial={{ col: 0, dir: "asc" }}
            rows={subnets.map((s) => ({
              id: s.id,
              sort: [
                ipKey(s.cidr),
                s.name,
                s.enabled ? "se escanea" : "pausada",
                timeKey(s.created_at),
              ],
              cells: (
                <>
                  <th scope="row" className="num">
                    {s.cidr}
                  </th>
                  <td>{s.name ?? <span className="text-faint">-</span>}</td>
                  <td>
                    <span
                      className="status"
                      data-state={s.enabled ? "ok" : undefined}
                    >
                      <span className="dot" aria-hidden="true" />
                      {s.enabled ? "se escanea" : "pausada"}
                    </span>
                  </td>
                  <td>
                    <When iso={s.created_at} />
                  </td>
                  {admin ? (
                    <td className="text-right">
                      <form action={setSubnetEnabled}>
                        <input type="hidden" name="id" value={s.id} />
                        <input
                          type="hidden"
                          name="enabled"
                          value={String(!s.enabled)}
                        />
                        <SubmitButton className="btn btn-sm" pendingText="...">
                          {s.enabled ? "Pausar" : "Habilitar"}
                        </SubmitButton>
                      </form>
                    </td>
                  ) : null}
                </>
              ),
            }))}
          />
        </TableRegion>
      ) : (
        <div className="panel">
          <Empty>
            No hay subnets.{" "}
            {admin
              ? "Agrega la primera arriba."
              : "Pedile a un admin que agregue una."}
          </Empty>
        </div>
      )}
    </>
  );
}
