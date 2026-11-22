// searchParams llegan del usuario: se normalizan antes de mandarlos a la API.
export type SP = Record<string, string | string[] | undefined>;

export function one(sp: SP, key: string): string | undefined {
  const v = sp[key];
  const s = Array.isArray(v) ? v[0] : v;
  return s?.trim() ? s.trim().slice(0, 200) : undefined;
}

export function oneOf<T extends string>(
  sp: SP,
  key: string,
  allowed: readonly T[],
): T | undefined {
  const v = one(sp, key);
  return allowed.includes(v as T) ? (v as T) : undefined;
}

export function intParam(
  sp: SP,
  key: string,
  min: number,
  max: number,
): number | undefined {
  const v = one(sp, key);
  if (v === undefined || !/^-?\d+$/.test(v)) return undefined;
  const n = Number(v);
  return n >= min && n <= max ? n : undefined;
}

export const MAC_RE = /^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$/i;
