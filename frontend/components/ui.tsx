import Link from "next/link";
import type { ReactNode } from "react";

import { ago, dateTime } from "@/lib/format";
import type { ScanStatus } from "@/lib/types";

export function PageHead({
  title,
  count,
  children,
}: {
  title: string;
  count?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-2">
      <h1 className="font-cond text-[20px] font-semibold leading-none">
        {title}
      </h1>
      {count !== undefined ? (
        <span className="num text-[13px] text-muted">{count}</span>
      ) : null}
      {children ? (
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {children}
        </div>
      ) : null}
    </div>
  );
}

const SCAN_LABEL: Record<ScanStatus, string> = {
  pending: "en cola",
  running: "escaneando",
  done: "terminado",
  failed: "fallo",
};

export function ScanState({ status }: { status: ScanStatus }) {
  return (
    <span className="status" data-state={status}>
      <span className="dot" aria-hidden="true" />
      {SCAN_LABEL[status]}
    </span>
  );
}

export function When({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="text-faint">-</span>;
  return (
    <time dateTime={iso} title={dateTime(iso)} className="num text-muted">
      {ago(iso)}
    </time>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="px-3 py-10 text-center text-[13px] text-muted">{children}</p>
  );
}

export function TableRegion({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  // Region con foco: quien navega con teclado puede desplazar la tabla horizontalmente.
  return (
    <div
      className="table-wrap panel"
      role="region"
      aria-label={label}
      tabIndex={0}
    >
      {children}
    </div>
  );
}

type Params = Record<string, string | undefined>;

export function hrefWith(base: string, params: Params, patch: Params): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...params, ...patch }))
    if (v) sp.set(k, v);
  const s = sp.toString();
  return s ? `${base}?${s}` : base;
}

/** Encabezado ordenable por URL (orden del lado del servidor, la pagina sigue funcionando sin JS). */
export function SortTh({
  label,
  field,
  base,
  params,
  defaultField,
}: {
  label: string;
  field: string;
  base: string;
  params: Params;
  defaultField: string;
}) {
  const current = params.sort ?? defaultField;
  const order = params.order ?? "asc";
  const active = current === field;
  const next = active && order === "asc" ? "desc" : "asc";
  return (
    <th
      scope="col"
      aria-sort={
        active ? (order === "asc" ? "ascending" : "descending") : undefined
      }
    >
      <Link
        href={hrefWith(base, params, {
          sort: field,
          order: next,
          offset: undefined,
        })}
        scroll={false}
      >
        {label}
      </Link>
    </th>
  );
}

export function Pager({
  base,
  params,
  total,
  limit,
  offset,
}: {
  base: string;
  params: Params;
  total: number;
  limit: number;
  offset: number;
}) {
  if (total <= limit) return null;
  const prev = Math.max(offset - limit, 0);
  const next = offset + limit;
  return (
    <nav
      aria-label="Paginas"
      className="mt-3 flex items-center justify-end gap-2 text-[13px] text-muted"
    >
      <span className="num">
        {offset + 1}-{Math.min(offset + limit, total)} de {total}
      </span>
      {offset > 0 ? (
        <Link
          className="btn btn-sm"
          href={hrefWith(base, params, {
            offset: prev ? String(prev) : undefined,
          })}
        >
          Anterior
        </Link>
      ) : null}
      {next < total ? (
        <Link
          className="btn btn-sm"
          href={hrefWith(base, params, { offset: String(next) })}
        >
          Siguiente
        </Link>
      ) : null}
    </nav>
  );
}
