"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { z } from "zod";

import { ApiError, apiFetch } from "@/lib/api";
import { SESSION_COOKIE, SESSION_MAX_AGE_S } from "@/lib/config";
import { safeNext } from "@/lib/safe-next";
import type { FormState, Me } from "@/lib/types";

const LoginSchema = z.object({
  username: z.string().trim().min(1).max(64),
  password: z.string().min(1).max(128),
});

export async function login(
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  const parsed = LoginSchema.safeParse({
    username: form.get("username"),
    password: form.get("password"),
  });
  if (!parsed.success) return { error: "Completa usuario y clave." };

  let token: string;
  try {
    ({ token } = await apiFetch<{ token: string; user: Me }>(
      "/api/auth/login",
      {
        method: "POST",
        body: parsed.data,
        token: null,
      },
    ));
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 429))
      return { error: e.message };
    return { error: "No se pudo contactar al servidor. Proba de nuevo." };
  }

  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true, // el JS de la pagina no puede leerla (XSS no roba la sesion)
    secure: true,
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  });
  redirect(safeNext(form.get("next")));
}

export async function logout(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (token) {
    try {
      await apiFetch("/api/auth/logout", { method: "POST", token });
    } catch {
      // Si la sesion ya habia vencido en la API, igual se borra la cookie.
    }
  }
  jar.delete({ name: SESSION_COOKIE, path: "/", secure: true });
  redirect("/login");
}
