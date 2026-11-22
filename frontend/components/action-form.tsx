"use client";

import { useActionState, useEffect, useRef, type ReactNode } from "react";

import type { FormState } from "@/lib/types";

/**
 * Formulario con resultado de una Server Action. El mensaje se anuncia en una region viva
 * y el formulario se limpia solo cuando la accion salio bien.
 */
export function ActionForm({
  action,
  children,
  className,
  resetOnSuccess = true,
}: {
  action: (prev: FormState, form: FormData) => Promise<FormState>;
  children: ReactNode;
  className?: string;
  resetOnSuccess?: boolean;
}) {
  const [state, formAction] = useActionState(action, undefined);
  const ref = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state?.ok && resetOnSuccess) ref.current?.reset();
  }, [state, resetOnSuccess]);

  return (
    <form ref={ref} action={formAction} className={className}>
      {children}
      <p
        role="status"
        aria-live="polite"
        className={`basis-full text-[13px] ${state?.error ? "text-crit" : "text-ok"}`}
      >
        {state?.error ?? state?.message ?? ""}
      </p>
    </form>
  );
}
