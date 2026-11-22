"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import { login } from "./actions";

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(login, undefined);
  const [show, setShow] = useState(false);
  const password = useRef<HTMLInputElement>(null);

  // Tras un error de credenciales, el foco vuelve a la clave para reintentar sin mouse.
  useEffect(() => {
    if (state?.error) password.current?.select();
  }, [state]);

  return (
    <form
      action={action}
      className="flex flex-col gap-4"
      aria-describedby={state?.error ? "login-error" : undefined}
    >
      <input type="hidden" name="next" value={next} />
      <div className="field">
        <label htmlFor="username">Usuario</label>
        <input
          id="username"
          name="username"
          className="input"
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="next"
          maxLength={64}
          required
          autoFocus
        />
      </div>
      <div className="field">
        <label htmlFor="current-password">Clave</label>
        <div className="flex gap-2">
          <input
            ref={password}
            id="current-password"
            name="password"
            type={show ? "text" : "password"}
            className="input flex-1"
            autoComplete="current-password"
            enterKeyHint="done"
            maxLength={128}
            required
          />
          <button
            type="button"
            className="btn btn-ghost btn-sm self-center"
            aria-pressed={show}
            aria-controls="current-password"
            onClick={() => setShow((s) => !s)}
          >
            {show ? "Ocultar" : "Mostrar"}
          </button>
        </div>
      </div>
      <p
        id="login-error"
        role="alert"
        className="min-h-5 text-[13px] text-crit"
      >
        {state?.error ?? ""}
      </p>
      <button type="submit" className="btn btn-primary" disabled={pending}>
        {pending ? "Entrando..." : "Entrar"}
      </button>
    </form>
  );
}
