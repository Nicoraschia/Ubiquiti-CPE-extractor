import { SIGNAL_CRIT, SIGNAL_OK, signalLevel } from "@/lib/signal";

const W = 400;
const H = 72;
const TOP = -40; // dBm en el borde superior
const BOTTOM = -90; // dBm en el borde inferior

const y = (dbm: number) =>
  ((TOP - Math.min(TOP, Math.max(BOTTOM, dbm))) / (TOP - BOTTOM)) * H;

/** Historial de senal sobre bandas de estado. Orden cronologico: el ultimo punto es el actual. */
export function Sparkline({
  points,
}: {
  points: { at: string; dbm: number }[];
}) {
  if (points.length < 2) {
    return (
      <p className="text-[13px] text-muted">
        Todavia no hay historial suficiente (hacen falta 2 escaneos).
      </p>
    );
  }
  const t0 = new Date(points[0].at).getTime();
  const t1 = new Date(points[points.length - 1].at).getTime();
  const x = (iso: string) =>
    t1 === t0 ? W : ((new Date(iso).getTime() - t0) / (t1 - t0)) * W;
  const last = points[points.length - 1];
  const values = points.map((p) => p.dbm);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="block h-full min-h-[96px] w-full"
      role="img"
      aria-label={`Senal entre ${min} y ${max} dBm en ${points.length} escaneos; actual ${last.dbm} dBm`}
    >
      <rect
        x="0"
        y="0"
        width={W}
        height={y(SIGNAL_OK)}
        fill="color-mix(in srgb, var(--ok) 11%, transparent)"
      />
      <rect
        x="0"
        y={y(SIGNAL_OK)}
        width={W}
        height={y(SIGNAL_CRIT) - y(SIGNAL_OK)}
        fill="color-mix(in srgb, var(--warn) 11%, transparent)"
      />
      <rect
        x="0"
        y={y(SIGNAL_CRIT)}
        width={W}
        height={H - y(SIGNAL_CRIT)}
        fill="color-mix(in srgb, var(--crit) 11%, transparent)"
      />
      <polyline
        fill="none"
        stroke="var(--text)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        points={points
          .map((p) => `${x(p.at).toFixed(1)},${y(p.dbm).toFixed(1)}`)
          .join(" ")}
      />
      <circle
        cx={W}
        cy={y(last.dbm)}
        r="3"
        fill={`var(--${signalLevel(last.dbm) === "none" ? "nodata" : signalLevel(last.dbm)})`}
      />
    </svg>
  );
}
