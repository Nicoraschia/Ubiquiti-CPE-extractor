const rtf = new Intl.RelativeTimeFormat("es-AR", {
  numeric: "auto",
  style: "short",
});
const dtf = new Intl.DateTimeFormat("es-AR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Argentina/Buenos_Aires",
});
const nf = new Intl.NumberFormat("es-AR");

export function ago(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "-";
  const s = Math.round((new Date(iso).getTime() - now) / 1000);
  const abs = Math.abs(s);
  if (abs < 60) return rtf.format(s, "second");
  if (abs < 3600) return rtf.format(Math.round(s / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(s / 3600), "hour");
  return rtf.format(Math.round(s / 86400), "day");
}

export function dateTime(iso: string | null | undefined): string {
  return iso ? dtf.format(new Date(iso)) : "-";
}

export function int(n: number | null | undefined): string {
  return n === null || n === undefined ? "-" : nf.format(n);
}

export function uptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "-";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  return `${d} d ${h} h`;
}

export function distance(m: number | null | undefined): string {
  if (m === null || m === undefined) return "-";
  return m >= 1000
    ? `${(m / 1000).toLocaleString("es-AR", { maximumFractionDigits: 1 })} km`
    : `${m} m`;
}

/** tshaper de airOS guarda kbps. */
export function plan(inKbps: number | null, outKbps: number | null): string {
  if (inKbps === null && outKbps === null) return "sin limite";
  const mbps = (v: number | null) =>
    v === null
      ? "-"
      : (v / 1000).toLocaleString("es-AR", { maximumFractionDigits: 1 });
  return `${mbps(inKbps)} / ${mbps(outKbps)} Mbps`;
}

const BRANDS: [RegExp, string][] = [
  [/huawei/i, "Huawei"],
  [/tp-?link|mercusys|mercury/i, "TP-Link"],
  [/mikrotik|routerboard/i, "MikroTik"],
  [/ubiquiti/i, "Ubiquiti"],
  [/tenda/i, "Tenda"],
  [/zte/i, "ZTE"],
  [/d-?link/i, "D-Link"],
  [/xiaomi/i, "Xiaomi"],
  [/samsung/i, "Samsung"],
  [/apple/i, "Apple"],
  [/privada/i, "MAC privada"],
];

/** Marca corta para mostrar junto al hostname; el fabricante completo queda en el title. */
export function brand(vendor: string | null | undefined): string | null {
  if (!vendor) return null;
  for (const [re, name] of BRANDS) if (re.test(vendor)) return name;
  const first = vendor.split(/[\s,]+/)[0];
  return first.charAt(0).toUpperCase() + first.slice(1).toLowerCase();
}
