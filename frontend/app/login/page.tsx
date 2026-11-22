import type { Metadata } from "next";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Entrar" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next, vencida } = await searchParams;
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="flex w-full max-w-[320px] flex-col gap-6">
        <header className="flex flex-col gap-1">
          <div
            aria-hidden="true"
            className="mb-3 grid size-8 place-items-center rounded-sm border-[1.5px] border-text font-mono text-[11px] font-semibold"
          >
            CS
          </div>
          <h1 className="font-cond text-[22px] font-semibold">CPE Scanner</h1>
          <p className="text-[13px] text-muted">
            Acceso para el equipo tecnico.
          </p>
        </header>
        {vencida ? (
          <p className="alert" data-tone="warn" role="status">
            Tu sesion vencio. Volve a entrar.
          </p>
        ) : null}
        <LoginForm next={typeof next === "string" ? next : ""} />
      </div>
    </main>
  );
}
