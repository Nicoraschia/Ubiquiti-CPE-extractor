"""Persistencia en Postgres. Una conexion, usada solo desde el hilo principal."""

import os
from importlib.resources import files

import psycopg
from psycopg.types.json import Jsonb


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"])


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(files("cpe_scanner").joinpath("schema.sql").read_text())
    conn.commit()


def add_subnet(conn: psycopg.Connection, cidr: str, name: str | None) -> int:
    row = conn.execute(
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
    return conn.execute(sql + " ORDER BY cidr").fetchall()


def start_scan(conn: psycopg.Connection, subnet_id: int | None) -> int:
    scan_id = conn.execute("INSERT INTO scans (subnet_id) VALUES (%s) RETURNING id", (subnet_id,)).fetchone()[0]
    conn.commit()
    return scan_id


def finish_scan(conn: psycopg.Connection, scan_id: int, alive: int, ok: int, failed: int) -> None:
    conn.execute(
        "UPDATE scans SET finished_at = now(), hosts_alive = %s, hosts_ok = %s, hosts_failed = %s WHERE id = %s",
        (alive, ok, failed, scan_id),
    )
    conn.commit()


# Un equipo escaneado por SSH es la fuente de verdad: pisa todos los campos.
_UPSERT_SSH = """
INSERT INTO devices (mac, device_id, ip, role, name, platform, firmware, ssid, ap_mac, signal,
                     netmode, shaper_in, shaper_out, config, cred_slot, source, last_seen, last_scan_id)
VALUES (%(mac)s, %(device_id)s, %(ip)s, %(role)s, %(name)s, %(platform)s, %(firmware)s, %(ssid)s,
        %(ap_mac)s, %(signal)s, %(netmode)s, %(shaper_in)s, %(shaper_out)s, %(config)s, %(cred_slot)s,
        'ssh', now(), %(scan_id)s)
ON CONFLICT (mac) DO UPDATE SET
    cred_slot = EXCLUDED.cred_slot,
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
    for s in r.get("stations", []):
        params = {**s, "ap_mac": r["mac"], "scan_id": scan_id}
        conn.execute(_UPSERT_STATION, params)
        conn.execute(_INSERT_LINK, params)
    for lease in r.get("leases", []):
        conn.execute(_INSERT_LEASE, {**lease, "cpe_mac": r["mac"], "scan_id": scan_id})
    conn.commit()


def cred_slots_by_ip(conn: psycopg.Connection) -> dict[str, int]:
    """IP -> credencial que funciono la ultima vez, para probarla primero."""
    rows = conn.execute("SELECT host(ip), cred_slot FROM devices WHERE cred_slot IS NOT NULL AND ip IS NOT NULL")
    return dict(rows.fetchall())


def list_devices(conn: psycopg.Connection, role: str | None, search: str | None) -> list[tuple]:
    sql = """
        SELECT d.mac::text, host(d.ip), d.role, d.name, d.platform, d.signal, d.source,
               ap.name AS ap_name
        FROM devices d LEFT JOIN devices ap ON ap.mac = d.ap_mac
        WHERE (%(role)s::text IS NULL OR d.role = %(role)s)
          AND (%(q)s::text IS NULL OR concat_ws(' ', d.name, d.platform, d.mac::text, host(d.ip), d.ssid) ILIKE %(q)s)
        ORDER BY ap.name NULLS FIRST, d.name
    """
    return conn.execute(sql, {"role": role, "q": f"%{search}%" if search else None}).fetchall()
