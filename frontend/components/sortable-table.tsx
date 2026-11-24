"use client";

import { useMemo, useState, type ReactNode } from "react";

import { compareValues, type SortDir, type SortValue } from "@/lib/sort";

import { SortIcon } from "./sort-icon";

/** Texto = columna ordenable. `hidden` = columna de acciones, con titulo solo para lectores de pantalla. */
type Column = string | { hidden: string };

export type TableRow = {
  id: string | number;
  level?: string;
  /** Valor crudo por columna (numero, texto o fecha en ms): no se ordena por el texto formateado. */
  sort: SortValue[];
  cells: ReactNode;
};

/**
 * Tabla con todas sus filas cargadas, que se ordena en el navegador. Las celdas las arma el servidor.
 * Para tablas paginadas usar SortTh: ordenar solo la pagina visible seria enganoso.
 */
export function SortableTable({
  columns,
  rows,
  initial,
}: {
  columns: Column[];
  rows: TableRow[];
  initial: { col: number; dir: SortDir };
}) {
  const [sort, setSort] = useState(initial);
  const [announcement, setAnnouncement] = useState("");
  const ordered = useMemo(
    () =>
      [...rows].sort((a, b) =>
        compareValues(a.sort[sort.col], b.sort[sort.col], sort.dir),
      ),
    [rows, sort],
  );

  function sortBy(col: number, label: string) {
    const dir: SortDir =
      sort.col === col && sort.dir === "asc" ? "desc" : "asc";
    setSort({ col, dir });
    setAnnouncement(
      `Ordenado por ${label}, ${dir === "asc" ? "ascendente" : "descendente"}`,
    );
  }

  return (
    <>
      <table className="data">
        <thead>
          <tr>
            {columns.map((c, i) =>
              typeof c === "string" ? (
                <th
                  key={c}
                  scope="col"
                  aria-sort={
                    sort.col !== i
                      ? undefined
                      : sort.dir === "asc"
                        ? "ascending"
                        : "descending"
                  }
                >
                  <button
                    type="button"
                    className="sort"
                    onClick={() => sortBy(i, c)}
                  >
                    {c}
                    <SortIcon />
                  </button>
                </th>
              ) : (
                <th key={c.hidden} scope="col">
                  <span className="visually-hidden">{c.hidden}</span>
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {ordered.map((r) => (
            <tr key={r.id} data-level={r.level}>
              {r.cells}
            </tr>
          ))}
        </tbody>
      </table>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
    </>
  );
}
