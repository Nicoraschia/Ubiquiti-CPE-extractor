import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import { ConfirmForm, SubmitButton } from "@/components/client";
import { SortableTable } from "@/components/sortable-table";
import { PageHead, TableRegion, When } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { requireAdmin } from "@/lib/session";
import { timeKey } from "@/lib/sort";
import type { User } from "@/lib/types";

import { createUser, resetPassword, updateUser } from "../actions";

export const metadata: Metadata = { title: "Usuarios" };

export default async function UsuariosPage() {
  const me = await requireAdmin();
  const users = await apiFetch<User[]>("/api/users");

  return (
    <>
      <PageHead
        title="Usuarios"
        count={`${users.filter((u) => u.enabled).length} activos`}
      />

      <ActionForm
        action={createUser}
        className="panel mb-4 flex flex-wrap items-end gap-3 p-4"
      >
        <div className="field">
          <label htmlFor="u-name">Usuario</label>
          <input
            id="u-name"
            name="username"
            className="input w-[180px]"
            required
            pattern="[a-zA-Z0-9._\-]{3,32}"
            maxLength={32}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
          />
          <span className="field-error">
            3 a 32: letras, numeros, punto o guion
          </span>
        </div>
        <div className="field">
          <label htmlFor="u-pass">Clave inicial</label>
          <input
            id="u-pass"
            name="password"
            type="password"
            className="input w-[220px]"
            required
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
          />
          <span className="field-error">Minimo 12 caracteres</span>
        </div>
        <div className="field">
          <label htmlFor="u-role">Rol</label>
          <select
            id="u-role"
            name="role"
            className="select"
            defaultValue="viewer"
          >
            <option value="viewer">viewer (solo lectura)</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <SubmitButton className="btn btn-primary" pendingText="Creando...">
          Crear usuario
        </SubmitButton>
      </ActionForm>

      <TableRegion label="Usuarios">
        <SortableTable
          columns={[
            "Usuario",
            "Rol",
            "Estado",
            "Ultimo login",
            "Sesiones",
            "Clave cambiada",
            { hidden: "Acciones" },
          ]}
          initial={{ col: 0, dir: "asc" }}
          rows={users.map((u) => {
            const self = u.id === me.id;
            return {
              id: u.id,
              sort: [
                u.username,
                u.role,
                u.enabled ? "activo" : "desactivado",
                timeKey(u.last_login_at),
                u.sessions,
                timeKey(u.password_changed_at),
              ],
              cells: (
                <>
                  <th scope="row">
                    {u.username}
                    {self ? (
                      <span className="ml-2 text-[12px] text-muted">(vos)</span>
                    ) : null}
                  </th>
                  <td className="num">{u.role}</td>
                  <td>
                    <span
                      className="status"
                      data-state={u.enabled ? "ok" : "off"}
                    >
                      <span className="dot" aria-hidden="true" />
                      {u.enabled ? "activo" : "desactivado"}
                    </span>
                  </td>
                  <td>
                    <When iso={u.last_login_at} />
                  </td>
                  <td className="num">{u.sessions}</td>
                  <td>
                    <When iso={u.password_changed_at} />
                  </td>
                  <td className="max-w-none">
                    {self ? (
                      <span className="text-[12px] text-faint">
                        tu clave se cambia en Cuenta
                      </span>
                    ) : (
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <form action={updateUser}>
                          <input type="hidden" name="id" value={u.id} />
                          <input
                            type="hidden"
                            name="role"
                            value={u.role === "admin" ? "viewer" : "admin"}
                          />
                          <SubmitButton
                            className="btn btn-sm"
                            pendingText="..."
                          >
                            {u.role === "admin"
                              ? "Pasar a viewer"
                              : "Hacer admin"}
                          </SubmitButton>
                        </form>
                        {u.enabled ? (
                          <ConfirmForm
                            action={updateUser}
                            message={`Desactivar a ${u.username}? Sus sesiones se cierran ya.`}
                          >
                            <input type="hidden" name="id" value={u.id} />
                            <input type="hidden" name="enabled" value="false" />
                            <SubmitButton
                              className="btn btn-sm btn-danger"
                              pendingText="..."
                            >
                              Desactivar
                            </SubmitButton>
                          </ConfirmForm>
                        ) : (
                          <form action={updateUser}>
                            <input type="hidden" name="id" value={u.id} />
                            <input type="hidden" name="enabled" value="true" />
                            <SubmitButton
                              className="btn btn-sm"
                              pendingText="..."
                            >
                              Reactivar
                            </SubmitButton>
                          </form>
                        )}
                        <details>
                          <summary className="btn btn-sm btn-ghost list-none">
                            Resetear clave
                          </summary>
                          <ActionForm
                            action={resetPassword}
                            className="mt-2 flex w-[280px] flex-col gap-2 whitespace-normal pb-2 text-left"
                          >
                            <input type="hidden" name="id" value={u.id} />
                            <div className="field">
                              <label htmlFor={`rp-${u.id}`}>
                                Clave nueva para {u.username}
                              </label>
                              <input
                                id={`rp-${u.id}`}
                                name="password"
                                type="password"
                                className="input"
                                required
                                minLength={12}
                                maxLength={128}
                                autoComplete="new-password"
                              />
                            </div>
                            <SubmitButton
                              className="btn btn-primary btn-sm"
                              pendingText="Guardando..."
                            >
                              Guardar clave
                            </SubmitButton>
                          </ActionForm>
                        </details>
                      </div>
                    )}
                  </td>
                </>
              ),
            };
          })}
        />
      </TableRegion>
    </>
  );
}
