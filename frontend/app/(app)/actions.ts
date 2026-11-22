"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { ApiError, apiFetch } from "@/lib/api";
import type { FormState } from "@/lib/types";

// Cada accion corre con la sesion del usuario: la API decide si tiene permiso (403 si es viewer).
// Los datos del formulario se validan aca y otra vez en la API.

async function run(
  fn: () => Promise<unknown>,
  okMessage: string,
  path: string,
): Promise<FormState> {
  try {
    await fn();
  } catch (e) {
    if (e instanceof ApiError)
      return {
        error: e.status === 403 ? "Necesitas rol admin para esto." : e.message,
      };
    throw e; // incluye el redirect al login si la sesion vencio
  }
  revalidatePath(path);
  return { ok: true, message: okMessage };
}

const Id = z.coerce.number().int().positive();

export async function requestScan(
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  const raw = form.get("subnet_id");
  const subnet = raw ? Id.safeParse(raw) : null;
  if (subnet && !subnet.success) return { error: "Subnet invalida." };
  let msg = "";
  const res = await run(
    async () => {
      const r = await apiFetch<{ queued: number[]; already_active: number[] }>(
        "/api/scans",
        {
          method: "POST",
          body: { subnet_id: subnet ? subnet.data : null },
        },
      );
      msg = r.queued.length
        ? `${r.queued.length} escaneo${r.queued.length > 1 ? "s" : ""} en cola.`
        : "Ya hay un escaneo en curso para esa subnet.";
    },
    "",
    "/escaneos",
  );
  return res?.ok ? { ok: true, message: msg } : res;
}

const SubnetIn = z.object({
  cidr: z
    .string()
    .trim()
    .regex(
      /^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/,
      "CIDR invalido, por ejemplo 192.168.18.0/24",
    ),
  name: z.string().trim().max(80).optional(),
});

export async function addSubnet(
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  const parsed = SubnetIn.safeParse({
    cidr: form.get("cidr"),
    name: form.get("name") || undefined,
  });
  if (!parsed.success) return { error: parsed.error.issues[0].message };
  return run(
    () => apiFetch("/api/subnets", { method: "POST", body: parsed.data }),
    `Subnet ${parsed.data.cidr} agregada.`,
    "/subnets",
  );
}

export async function setSubnetEnabled(form: FormData): Promise<void> {
  const id = Id.parse(form.get("id"));
  const enabled = form.get("enabled") === "true";
  await apiFetch(`/api/subnets/${id}`, { method: "PATCH", body: { enabled } });
  revalidatePath("/subnets");
}

const Password = z
  .string()
  .min(12, "La clave necesita al menos 12 caracteres.")
  .max(128);

const UserIn = z.object({
  username: z
    .string()
    .trim()
    .toLowerCase()
    .regex(
      /^[a-z0-9._-]{3,32}$/,
      "Usuario: 3 a 32 caracteres a-z, 0-9, punto o guion.",
    ),
  password: Password,
  role: z.enum(["admin", "viewer"]),
});

export async function createUser(
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  const parsed = UserIn.safeParse({
    username: form.get("username"),
    password: form.get("password"),
    role: form.get("role"),
  });
  if (!parsed.success) return { error: parsed.error.issues[0].message };
  return run(
    () => apiFetch("/api/users", { method: "POST", body: parsed.data }),
    `Usuario ${parsed.data.username} creado.`,
    "/usuarios",
  );
}

const UserPatch = z.object({
  id: Id,
  role: z.enum(["admin", "viewer"]).optional(),
  enabled: z
    .enum(["true", "false"])
    .transform((v) => v === "true")
    .optional(),
});

export async function updateUser(form: FormData): Promise<void> {
  const parsed = UserPatch.parse({
    id: form.get("id"),
    role: form.get("role") ?? undefined,
    enabled: form.get("enabled") ?? undefined,
  });
  const { id, ...body } = parsed;
  await apiFetch(`/api/users/${id}`, { method: "PATCH", body });
  revalidatePath("/usuarios");
}

export async function resetPassword(
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  const id = Id.safeParse(form.get("id"));
  const pw = Password.safeParse(form.get("password"));
  if (!id.success) return { error: "Usuario invalido." };
  if (!pw.success) return { error: pw.error.issues[0].message };
  return run(
    () =>
      apiFetch(`/api/users/${id.data}`, {
        method: "PATCH",
        body: { password: pw.data },
      }),
    "Clave cambiada. Sus sesiones abiertas se cerraron.",
    "/usuarios",
  );
}

export async function changeOwnPassword(
  _prev: FormState,
  form: FormData,
): Promise<FormState> {
  const current = z
    .string()
    .min(1)
    .max(128)
    .safeParse(form.get("current_password"));
  const next = Password.safeParse(form.get("new_password"));
  if (!current.success) return { error: "Ingresa tu clave actual." };
  if (!next.success) return { error: next.error.issues[0].message };
  if (next.data !== form.get("confirm_password"))
    return { error: "La clave nueva y su repeticion no coinciden." };
  // La API mantiene esta sesion y cierra las demas.
  return run(
    () =>
      apiFetch("/api/auth/password", {
        method: "POST",
        body: { current_password: current.data, new_password: next.data },
      }),
    "Clave cambiada. Se cerraron tus otras sesiones.",
    "/cuenta",
  );
}
