import { signalBars, signalLabel, signalLevel } from "@/lib/signal";

export function SignalMeter({
  dbm,
  bars = true,
}: {
  dbm: number | null | undefined;
  bars?: boolean;
}) {
  const lit = signalBars(dbm);
  return (
    <span
      className="sig"
      data-level={signalLevel(dbm)}
      role="img"
      aria-label={signalLabel(dbm)}
    >
      {bars ? (
        <span className="bars" aria-hidden="true">
          {[1, 2, 3, 4].map((n) => (
            <i key={n} data-lit={n <= lit ? "" : undefined} />
          ))}
        </span>
      ) : null}
      <span className="v" aria-hidden="true">
        {dbm ?? "-"}
      </span>
    </span>
  );
}
