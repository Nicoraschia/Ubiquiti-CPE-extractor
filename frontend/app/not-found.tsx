import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-[60dvh] place-items-center px-4 text-center">
      <div>
        <p className="label-caps">404</p>
        <h1 className="mt-2 font-cond text-[22px] font-semibold">
          No existe o no tenes acceso
        </h1>
        <Link href="/equipos" className="btn mt-4">
          Volver a equipos
        </Link>
      </div>
    </main>
  );
}
