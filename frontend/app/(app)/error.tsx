"use client";

// No se muestra el mensaje del error: en produccion Next lo oculta y podria tener detalles internos.
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="panel mx-auto mt-10 max-w-[480px] p-6">
      <p className="label-caps text-crit">Error</p>
      <h1 className="mt-2 font-cond text-[20px] font-semibold">
        No se pudo cargar esta pantalla
      </h1>
      <p className="mt-2 text-[13px] text-muted">
        Puede ser que la API no responda. Si se repite, pasale este codigo a
        quien mantiene el sistema:{" "}
        <span className="num">{error.digest ?? "sin codigo"}</span>
      </p>
      <button type="button" className="btn mt-4" onClick={reset}>
        Reintentar
      </button>
    </div>
  );
}
