"""Persistencia en Postgres. Una conexion, usada solo desde el hilo principal."""

import ipaddress
import os
from importlib.resources import files

import psycopg
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb


def _tuples(conn: psycopg.Connection) -> psycopg.Cursor:
    # Estas funciones leen filas por posicion; la API usa conexiones con dict_row.
    return conn.cursor(row_factory=tuple_row)


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"])


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(files("cpe_scanner").joinpath("schema.sql").read_text())
    conn.commit()


def add_subnet(conn: psycopg.Connection, cidr: str, name: str | None) -> int:
    # Postgres rechaza bits de host en un cidr (192.168.15.77/24): se normaliza a la red.
    cidr = str(ipaddress.ip_network(cidr, strict=False))
    row = _tuples(conn).execute(
        """INSERT INTO subnets (cidr, name) VALUES (%s, %s)
           ON CONFLICT (cidr) DO UPDATE SET name = COALESCE(EXCLUDED.name, subnets.name)
           RETURNING id""",
        (cidr, name),
    ).fetchone()
    conn.commit()
    return row[0]


def list_subnets(conn: psycopg.Connection, only_enabled: bool = False) -> list[tuple]:
    sql = "SELECT id, cidr::text, name, enabled FROM subnets"
    if only_enabled:
        sql += " WHERE enabled"
    return _tuples(conn).execute(sql + " ORDER BY cidr").fetchall()


_ACTIVE = "ON CONFLICT (subnet_id) WHERE status IN ('pending', 'running') DO NOTHING"


def start_scan(conn: psycopg.Connection, subnet_id: int | None, trigger: str = "cli") -> int | None:
    """Escaneo que arranca ya (CLI). None si esa subnet ya tiene uno pendiente o corriendo."""
    row = _tuples(conn).execute(
        f"INSERT INTO scans (subnet_id, status, trigger) VALUES (%s, 'running', %s) {_ACTIVE} RETURNING id",
        (subnet_id, trigger),
    ).fetchone()
    conn.commit()
    return row[0] if row else None


def enqueue_scan(conn: psycopg.Connection, subnet_id: int, trigger: str) -> int | None:
    """Encola para el worker. None si esa subnet ya tiene uno pendiente o corriendo."""
    row = _tuples(conn).execute(
        f"INSERT INTO scans (subnet_id, status, trigger) VALUES (%s, 'pending', %s) {_ACTIVE} RETURNING id",
        (subnet_id, trigger),
    ).fetchone()
    conn.commit()
    return row[0] if row else None


def claim_scan(conn: psycopg.Connection) -> tuple[int, int, str, str | None] | None:
    """Toma el escaneo pendiente mas viejo. SKIP LOCKED permite varios workers sin pisarse."""
    row = _tuples(conn).execute(
        """UPDATE scans s SET status = 'running', started_at = now()
           FROM subnets n
           WHERE n.id = s.subnet_id AND s.id = (
               SELECT id FROM scans WHERE status = 'pending' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
           RETURNING s.id, s.subnet_id, n.cidr::text, n.name"""
    ).fetchone()
    conn.commit()
    return row


def finish_scan(
    conn: psycopg.Connection, scan_id: int, alive: int | None, ok: int | None, failed: int | None,
    status: str = "done", error: str | None = None,
) -> None:
    conn.execute(
        """UPDATE scans SET finished_at = now(), hosts_alive = %s, hosts_ok = %s, hosts_failed = %s,
                            status = %s, error = %s
           WHERE id = %s""",
        (alive, ok, failed, status, error, scan_id),
    )
    conn.commit()


def fail_stale_scans(conn: psycopg.Connection) -> int:
    """Al arrancar el worker: lo que quedo 'running' murio con el proceso anterior.

    Los del CLI pueden estar corriendo en otro contenedor; solo se liberan si llevan
    mas de una hora (un /24 tarda segundos), para que no bloqueen la subnet para siempre.
    """
    n = conn.execute(
        """UPDATE scans SET status = 'failed', finished_at = now(), error = 'proceso interrumpido durante el escaneo'
           WHERE status = 'running'
             AND (trigger IS DISTINCT FROM 'cli' OR started_at < now() - interval '1 hour')"""
    ).rowcount
    conn.commit()
    return n


# Un equipo escaneado por SSH es la fuente de verdad: pisa todos los campos.
_UPSERT_SSH = """
INSERT INTO devices (mac, device_id, ip, role, name, platform, firmware, ssid, ap_mac, signal,
                     netmode, shaper_in, shaper_out, config, cred_slot, source, last_seen, last_scan_id,
                     ssh_scan_id)
VALUES (%(mac)s, %(device_id)s, %(ip)s, %(role)s, %(name)s, %(platform)s, %(firmware)s, %(ssid)s,
        %(ap_mac)s, %(signal)s, %(netmode)s, %(shaper_in)s, %(shaper_out)s, %(config)s, %(cred_slot)s,
        'ssh', now(), %(scan_id)s, %(scan_id)s)
ON CONFLICT (mac) DO UPDATE SET
    cred_slot = EXCLUDED.cred_slot, ssh_scan_id = EXCLUDED.ssh_scan_id,
    device_id = EXCLUDED.device_id, ip = EXCLUDED.ip, role = EXCLUDED.role, name = EXCLUDED.name,
    platform = EXCLUDED.platform, firmware = EXCLUDED.firmware, ssid = EXCLUDED.ssid,
    ap_mac = EXCLUDED.ap_mac, signal = EXCLUDED.signal, netmode = EXCLUDED.netmode,
    shaper_in = EXCLUDED.shaper_in, shaper_out = EXCLUDED.shaper_out, config = EXCLUDED.config,
    source = 'ssh', last_seen = now(), last_scan_id = EXCLUDED.last_scan_id
"""

# Visto desde el AP: solo actualiza lo que wstalist sabe; no pisa datos de un escaneo SSH.
_UPSERT_STATION = """
INSERT INTO devices (mac, ip, role, name, platform, firmware, ap_mac, signal, source, last_seen, last_scan_id)
VALUES (%(mac)s, %(ip)s, 'cpe', %(name)s, %(platform)s, %(firmware)s, %(ap_mac)s, %(remote_signal)s,
        'wstalist', now(), %(scan_id)s)
ON CONFLICT (mac) DO UPDATE SET
    ip = COALESCE(EXCLUDED.ip, devices.ip), name = COALESCE(EXCLUDED.name, devices.name),
    platform = COALESCE(EXCLUDED.platform, devices.platform),
    firmware = COALESCE(EXCLUDED.firmware, devices.firmware),
    ap_mac = EXCLUDED.ap_mac, signal = EXCLUDED.signal,
    last_seen = now(), last_scan_id = EXCLUDED.last_scan_id
"""

_INSERT_LINK = """
INSERT INTO ap_links (scan_id, ap_mac, cpe_mac, cpe_ip, signal, remote_signal, noisefloor,
                      distance_m, dl_linkscore, ul_linkscore, uptime_s)
VALUES (%(scan_id)s, %(ap_mac)s, %(mac)s, %(ip)s, %(signal)s, %(remote_signal)s, %(noisefloor)s,
        %(distance_m)s, %(dl_linkscore)s, %(ul_linkscore)s, %(uptime_s)s)
ON CONFLICT (scan_id, cpe_mac) DO NOTHING
"""

_INSERT_LEASE = """
INSERT INTO lan_leases (scan_id, cpe_mac, mac, ip, hostname, client_id, lease_time)
VALUES (%(scan_id)s, %(cpe_mac)s, %(mac)s, %(ip)s, %(hostname)s, %(client_id)s, %(lease_time)s)
ON CONFLICT (scan_id, cpe_mac, mac) DO NOTHING
"""


def save_result(conn: psycopg.Connection, scan_id: int, r: dict) -> None:
    if not r["ok"] or not r.get("mac"):
        error = r.get("error") or "sin MAC: no se pudo identificar el equipo"
        conn.execute("INSERT INTO scan_errors (scan_id, host, error) VALUES (%s, %s, %s)", (scan_id, r["host"], error))
        conn.commit()
        return

    conn.execute(_UPSERT_SSH, {**r, "ip": r["host"], "config": Jsonb(r["config"]), "scan_id": scan_id})
    if r.get("host_key"):
        # Nunca pisa una clave distinta: el collector ya rechazo esa conexion antes de llegar aca.
        conn.execute(
            """INSERT INTO ssh_host_keys (ip, key_type, key_b64) VALUES (%s, %s, %s)
               ON CONFLICT (ip) DO UPDATE SET last_seen = now()
               WHERE ssh_host_keys.key_type = EXCLUDED.key_type AND ssh_host_keys.key_b64 = EXCLUDED.key_b64""",
            (r["host"], *r["host_key"]),
        )
    for s in r.get("stations", []):
        params = {**s, "ap_mac": r["mac"], "scan_id": scan_id}
        conn.execute(_UPSERT_STATION, params)
        conn.execute(_INSERT_LINK, params)
    for lease in r.get("leases", []):
        conn.execute(_INSERT_LEASE, {**lease, "cpe_mac": r["mac"], "scan_id": scan_id})
    conn.commit()


def cred_slots_by_ip(conn: psycopg.Connection) -> dict[str, int]:
    """IP -> credencial que funciono la ultima vez, para probarla primero."""
    rows = _tuples(conn).execute("SELECT host(ip), cred_slot FROM devices WHERE cred_slot IS NOT NULL AND ip IS NOT NULL")
    return dict(rows.fetchall())


def host_keys(conn: psycopg.Connection) -> dict[str, tuple[str, str]]:
    """IP -> host key registrada, para verificar cada equipo antes de mandarle credenciales."""
    rows = _tuples(conn).execute("SELECT host(ip), key_type, key_b64 FROM ssh_host_keys").fetchall()
    return {ip: (kt, kb) for ip, kt, kb in rows}


def forget_host_key(conn: psycopg.Connection, ip: str) -> bool:
    """Equipo reemplazado legitimamente: el proximo escaneo registra su clave nueva."""
    row = _tuples(conn).execute("DELETE FROM ssh_host_keys WHERE ip = %s::inet RETURNING ip", (ip,)).fetchone()
    conn.commit()
    return row is not None


def list_devices(conn: psycopg.Connection, role: str | None, search: str | None) -> list[tuple]:
    sql = """
        SELECT d.mac::text, host(d.ip), d.role, d.name, d.platform, d.signal, d.source,
               ap.name AS ap_name
        FROM devices d LEFT JOIN devices ap ON ap.mac = d.ap_mac
        WHERE (%(role)s::text IS NULL OR d.role = %(role)s)
          AND (%(q)s::text IS NULL OR concat_ws(' ', d.name, d.platform, d.mac::text, host(d.ip), d.ssid) ILIKE %(q)s)
        ORDER BY ap.name NULLS FIRST, d.name
    """
    return _tuples(conn).execute(sql, {"role": role, "q": f"%{search}%" if search else None}).fetchall()
