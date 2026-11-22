import "server-only";

import { notFound } from "next/navigation";
import { cache } from "react";

import { apiFetch } from "./api";
import type { Me } from "./types";

// Una consulta a la API por request, compartida entre layout, paginas y acciones.
export const getMe = cache(() => apiFetch<Me>("/api/auth/me"));

/** Para paginas solo-admin. La API igual rechaza con 403: esto solo evita mostrar la pantalla. */
export async function requireAdmin(): Promise<Me> {
  const me = await getMe();
  if (me.role !== "admin") notFound();
  return me;
}
