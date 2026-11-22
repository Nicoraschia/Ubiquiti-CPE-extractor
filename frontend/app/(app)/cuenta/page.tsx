import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import { SubmitButton } from "@/components/client";
import { PageHead } from "@/components/ui";
import { getMe } from "@/lib/session";

import { changeOwnPassword } from "../actions";

export const metadata: Metadata = { title: "Cuenta" };

export default async function CuentaPage() {
  const me = await getMe();
  return (
    <>
      <PageHead title="Cuenta" count={`${me.username} · ${me.role}`} />
      <ActionForm
        action={changeOwnPassword}
        className="panel flex max-w-[420px] flex-col gap-4 p-4"
      >
        <h2 className="label-caps">Cambiar clave</h2>
        {/* username oculto: los gestores de claves asocian la clave nueva al usuario correcto */}
        <input
          type="text"
          name="username"
          autoComplete="username"
          value={me.username}
          readOnly
          hidden
        />
        <div className="field">
          <label htmlFor="c-cur">Clave actual</label>
          <input
            id="c-cur"
            name="current_password"
            type="password"
            className="input"
            required
            maxLength={128}
            autoComplete="current-password"
          />
        </div>
        <div className="field">
          <label htmlFor="c-new">Clave nueva</label>
          <input
            id="c-new"
            name="new_password"
            type="password"
            className="input"
            required
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
          />
          <span className="field-error">
            Minimo 12 caracteres, sin incluir tu usuario
          </span>
        </div>
        <div className="field">
          <label htmlFor="c-rep">Repetir clave nueva</label>
          <input
            id="c-rep"
            name="confirm_password"
            type="password"
            className="input"
            required
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
          />
        </div>
        <SubmitButton className="btn btn-primary" pendingText="Guardando...">
          Cambiar clave
        </SubmitButton>
      </ActionForm>
    </>
  );
}
