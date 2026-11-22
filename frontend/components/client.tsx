"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useFormStatus } from "react-dom";

export function SubmitButton({
  children,
  pendingText,
  className = "btn",
}: {
  children: ReactNode;
  pendingText?: string;
  className?: string;
}) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className={className} disabled={pending}>
      {pending && pendingText ? pendingText : children}
    </button>
  );
}

/** Refresca la pagina (datos del servidor) mientras haya algo en curso, p. ej. un escaneo. */
export function AutoRefresh({
  active,
  everyMs = 4000,
}: {
  active: boolean;
  everyMs?: number;
}) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, everyMs);
    return () => clearInterval(id);
  }, [active, everyMs, router]);
  return null;
}

/** Pide confirmacion nativa antes de enviar un formulario destructivo. */
export function ConfirmForm({
  action,
  message,
  children,
  className,
}: {
  action: (form: FormData) => void | Promise<void>;
  message: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <form
      action={action}
      className={className}
      onSubmit={(e) => {
        if (!window.confirm(message)) e.preventDefault();
      }}
    >
      {children}
    </form>
  );
}
