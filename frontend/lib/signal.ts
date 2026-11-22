// Umbrales airOS (dBm). Unico lugar donde viven: DESIGN.md los referencia.
export const SIGNAL_OK = -65;
export const SIGNAL_CRIT = -75;

export type SignalLevel = "ok" | "warn" | "crit" | "none";

export function signalLevel(dbm: number | null | undefined): SignalLevel {
  if (dbm === null || dbm === undefined) return "none";
  if (dbm >= SIGNAL_OK) return "ok";
  if (dbm >= SIGNAL_CRIT) return "warn";
  return "crit";
}

const LABELS: Record<SignalLevel, string> = {
  ok: "buena",
  warn: "atencion",
  crit: "critica",
  none: "sin datos",
};

export function signalLabel(dbm: number | null | undefined): string {
  const level = signalLevel(dbm);
  return level === "none"
    ? "Senal sin datos"
    : `Senal ${dbm} dBm, ${LABELS[level]}`;
}

/** Barras encendidas (1-4): la forma comunica el nivel sin depender del color. */
export function signalBars(dbm: number | null | undefined): number {
  if (dbm === null || dbm === undefined) return 0;
  if (dbm >= -55) return 4;
  if (dbm >= SIGNAL_OK) return 3;
  if (dbm >= SIGNAL_CRIT) return 2;
  return 1;
}
