export type SortDir = "asc" | "desc";
export type SortValue = string | number | null | undefined;

// "es": la ñ va despues de la n. numeric: AP_2 antes que AP_10. base: ignora mayusculas y acentos.
const collator = new Intl.Collator("es", {
  numeric: true,
  sensitivity: "base",
});

const isEmpty = (v: SortValue) => v === null || v === undefined || v === "";

/** Los vacios van siempre al final, en los dos sentidos: nunca tapan los datos. */
export function compareValues(
  a: SortValue,
  b: SortValue,
  dir: SortDir,
): number {
  if (isEmpty(a) || isEmpty(b)) return Number(isEmpty(a)) - Number(isEmpty(b));
  const r =
    typeof a === "number" && typeof b === "number"
      ? a - b
      : collator.compare(String(a), String(b));
  return dir === "asc" ? r : -r;
}

/** IPv4 o CIDR como numero: 192.168.9.2 va antes que 192.168.9.10. */
export function ipKey(ip: string | null | undefined): number | null {
  const m = ip?.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)(?:\/(\d+))?$/);
  if (!m) return null;
  const [a, b, c, d, mask] = m.slice(1).map((x) => Number(x ?? 32));
  return (((a * 256 + b) * 256 + c) * 256 + d) * 64 + mask;
}

export function timeKey(iso: string | null | undefined): number | null {
  return iso ? new Date(iso).getTime() : null;
}
