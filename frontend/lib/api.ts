import "server-only";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

import { SESSION_COOKIE } from "./config";

// Red interna de docker: el navegador nunca habla con la API ni ve el token.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

async function clientIp(): Promise<string | undefined> {
  // Caddy es el unico punto de entrada y reemplaza X-Forwarded-For con la IP real del cliente.
  return (
    (await headers()).get("x-forwarded-for")?.split(",")[0]?.trim() || undefined
  );
}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail))
      return body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    // cuerpo no JSON: se usa el status
  }
  return `error ${res.status}`;
}

export async function apiFetch<T>(
  path: string,
  init: {
    method?: string;
    query?: Query;
    body?: unknown;
    token?: string | null;
  } = {},
): Promise<T> {
  const token =
    init.token === undefined
      ? (await cookies()).get(SESSION_COOKIE)?.value
      : init.token;
  const url = new URL(path, API_URL);
  for (const [k, v] of Object.entries(init.query ?? {})) {
    if (v !== undefined && v !== null && v !== "")
      url.searchParams.set(k, String(v));
  }
  const ip = await clientIp();
  const res = await fetch(url, {
    method: init.method ?? "GET",
    cache: "no-store",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
      ...(ip ? { "X-Client-IP": ip } : {}),
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    signal: AbortSignal.timeout(15_000),
  });

  if (res.status === 401 && init.token === undefined) {
    // Sesion vencida o revocada: el login la reemplaza.
    redirect("/login?vencida=1");
  }
  if (!res.ok) throw new ApiError(res.status, await detail(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
