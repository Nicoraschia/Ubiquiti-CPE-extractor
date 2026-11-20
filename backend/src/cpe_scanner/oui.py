"""Fabricante por prefijo de MAC (OUI), desde la lista publica MA-L de IEEE."""

import csv
import io
import logging
import urllib.request

import psycopg
from psycopg.rows import tuple_row

log = logging.getLogger("cpe_scanner.oui")

IEEE_URL = "https://standards-oui.ieee.org/oui/oui.csv"
MAX_AGE_DAYS = 7


def parse_oui_csv(text: str) -> list[tuple[str, str]]:
    """Filas (prefijo 'AABBCC', fabricante). Ignora filas sin prefijo valido."""
    rows = {}
    for r in csv.DictReader(io.StringIO(text)):
        prefix = (r.get("Assignment") or "").strip().upper()
        vendor = (r.get("Organization Name") or "").strip()
        if len(prefix) == 6 and vendor and all(c in "0123456789ABCDEF" for c in prefix):
            rows[prefix] = vendor  # IEEE repite algunos prefijos; gana el ultimo
    return sorted(rows.items())


def download(url: str = IEEE_URL, timeout: float = 60) -> list[tuple[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "cpe-scanner"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return parse_oui_csv(r.read().decode("utf-8"))


def replace_vendors(conn: psycopg.Connection, rows: list[tuple[str, str]]) -> int:
    """Reemplaza la tabla completa en una transaccion: nunca queda a medio cargar."""
    if not rows:
        raise ValueError("lista OUI vacia: no se reemplaza la existente")
    conn.execute("DELETE FROM oui_vendors")
    with conn.cursor().copy("COPY oui_vendors (prefix, vendor) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    conn.commit()
    return len(rows)


def is_stale(conn: psycopg.Connection, max_age_days: int = MAX_AGE_DAYS) -> bool:
    (stale,) = conn.cursor(row_factory=tuple_row).execute(
        "SELECT coalesce(max(updated_at) < now() - make_interval(days => %s), true) FROM oui_vendors",
        (max_age_days,),
    ).fetchone()
    return stale


def refresh_if_stale(conn: psycopg.Connection) -> None:
    """Para el worker: si falla la descarga, sigue con la lista que ya habia."""
    if not is_stale(conn):
        return
    try:
        n = replace_vendors(conn, download())
        log.info("lista OUI actualizada: %s fabricantes", n)
    except Exception as e:
        conn.rollback()
        log.warning("no se pudo actualizar la lista OUI (%s: %s); se usa la existente", type(e).__name__, e)
