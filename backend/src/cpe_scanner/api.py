"""API HTTP de solo lectura sobre el inventario, mas alta de subnets y pedido de escaneos.

Todo bajo token Bearer (API_TOKEN): devuelve nombres de clientes.
"""

import ipaddress
import os
import secrets
from collections.abc import Iterator
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator

from . import db

MAC_RE = r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"


def get_conn() -> Iterator[psycopg.Connection]:
    with db.connect() as conn:
        conn.row_factory = dict_row
        yield conn


# Esquema de seguridad declarado: /docs muestra el boton Authorize y manda el header.
# (Swagger UI ignora un parametro de header llamado Authorization.)
bearer = HTTPBearer(auto_error=False, description="Token de API_TOKEN en el .env del servidor")


def require_token(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    token = os.environ.get("API_TOKEN")
    if not token:
        raise HTTPException(503, "API_TOKEN no configurado en el servidor")
    if creds is None or not secrets.compare_digest(creds.credentials.encode(), token.encode()):
        raise HTTPException(401, "token invalido", headers={"WWW-Authenticate": "Bearer"})


Conn = Annotated[psycopg.Connection, Depends(get_conn)]
app = FastAPI(title="CPE Scanner API", version="0.2.0")
api = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


@app.get("/health")
def health(conn: Conn) -> dict:
    conn.execute("SELECT 1")
    return {"status": "ok"}


# ---------- subnets ----------

class SubnetIn(BaseModel):
    cidr: str
    name: str | None = None

    @field_validator("cidr")
    @classmethod
    def valid_cidr(cls, v: str) -> str:
        try:
            return str(ipaddress.ip_network(v, strict=False))
        except ValueError as e:
            raise ValueError(f"CIDR invalido: {v}") from e


class SubnetPatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None


_SUBNET_COLS = "id, cidr::text AS cidr, name, enabled, created_at"


@api.get("/subnets")
def list_subnets(conn: Conn) -> list[dict]:
    return conn.execute(f"SELECT {_SUBNET_COLS} FROM subnets ORDER BY cidr").fetchall()


@api.post("/subnets", status_code=201)
def create_subnet(body: SubnetIn, conn: Conn) -> dict:
    sid = db.add_subnet(conn, body.cidr, body.name)
    return conn.execute(f"SELECT {_SUBNET_COLS} FROM subnets WHERE id = %s", (sid,)).fetchone()


@api.patch("/subnets/{subnet_id}")
def update_subnet(subnet_id: int, body: SubnetPatch, conn: Conn) -> dict:
    row = conn.execute(
        f"""UPDATE subnets SET name = COALESCE(%s, name), enabled = COALESCE(%s, enabled)
            WHERE id = %s RETURNING {_SUBNET_COLS}""",
        (body.name, body.enabled, subnet_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "subnet inexistente")
    conn.commit()
    return row


# ---------- devices ----------

_SORTS = {
    "name": "d.name", "signal": "d.signal", "ip": "d.ip", "platform": "d.platform",
    "last_seen": "d.last_seen", "ap": "ap.name",
}

_DEVICE_FILTERS = """
FROM devices d LEFT JOIN devices ap ON ap.mac = d.ap_mac
WHERE (%(role)s::text IS NULL OR d.role = %(role)s)
  AND (%(ap)s::macaddr IS NULL OR d.ap_mac = %(ap)s::macaddr)
  AND (%(platform)s::text IS NULL OR d.platform ILIKE %(platform)s)
  AND (%(source)s::text IS NULL OR d.source = %(source)s)
  AND (%(signal_max)s::int IS NULL OR d.signal <= %(signal_max)s)
  AND (%(q)s::text IS NULL OR concat_ws(' ', d.name, d.platform, d.firmware, d.mac::text, host(d.ip),
                                         d.ssid, ap.name) ILIKE %(q)s)
  AND (%(lan)s::text IS NULL OR EXISTS (
        SELECT 1 FROM current_leases cl
        WHERE cl.cpe_mac = d.mac AND concat_ws(' ', cl.hostname, cl.vendor, cl.mac::text, host(cl.ip)) ILIKE %(lan)s))
"""


def _like(v: str | None) -> str | None:
    # '_' y '%' son comodines de LIKE: "AP_TEST" no debe matchear "AP-TEST".
    if not v:
        return None
    return "%" + v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@api.get("/devices")
def list_devices(
    conn: Conn,
    q: Annotated[str | None, Query(description="nombre, modelo, firmware, MAC, IP, SSID o AP")] = None,
    role: Literal["ap", "cpe", "unknown"] | None = None,
    ap: Annotated[str | None, Query(pattern=MAC_RE, description="MAC del AP")] = None,
    platform: str | None = None,
    lan: Annotated[str | None, Query(description="router LAN: hostname, fabricante, MAC o IP del lease")] = None,
    source: Literal["ssh", "wstalist"] | None = None,
    signal_max: Annotated[int | None, Query(description="senal <= este valor (ej. -70)")] = None,
    sort: Literal["name", "signal", "ip", "platform", "last_seen", "ap"] = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    params = {
        "q": _like(q), "role": role, "ap": ap, "platform": _like(platform), "lan": _like(lan),
        "source": source, "signal_max": signal_max, "limit": limit, "offset": offset,
    }
    total = conn.execute(f"SELECT count(*) AS n {_DEVICE_FILTERS}", params).fetchone()["n"]
    items = conn.execute(
        f"""SELECT d.mac::text AS mac, host(d.ip) AS ip, d.role, d.name, d.platform, d.firmware, d.ssid,
                   d.signal, d.netmode, d.shaper_in, d.shaper_out, d.source, d.last_seen,
                   d.ap_mac::text AS ap_mac, ap.name AS ap_name,
                   (SELECT array_agg(DISTINCT coalesce(cl.hostname, cl.mac::text))
                      FROM current_leases cl WHERE cl.cpe_mac = d.mac) AS lan_hosts,
                   (SELECT array_agg(DISTINCT cl.vendor) FILTER (WHERE cl.vendor IS NOT NULL)
                      FROM current_leases cl WHERE cl.cpe_mac = d.mac) AS lan_vendors
            {_DEVICE_FILTERS}
            ORDER BY {_SORTS[sort]} {order} NULLS LAST, d.mac
            LIMIT %(limit)s OFFSET %(offset)s""",
        params,
    ).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@api.get("/devices/{mac}")
def get_device(mac: Annotated[str, Path(pattern=MAC_RE)], conn: Conn) -> dict:
    device = conn.execute(
        """SELECT d.mac::text AS mac, d.device_id::text AS device_id, host(d.ip) AS ip, d.role, d.name,
                  d.platform, d.firmware, d.ssid, d.signal, d.netmode, d.shaper_in, d.shaper_out, d.config,
                  d.source, d.last_seen, d.ap_mac::text AS ap_mac, ap.name AS ap_name, host(ap.ip) AS ap_ip
           FROM devices d LEFT JOIN devices ap ON ap.mac = d.ap_mac
           WHERE d.mac = %s::macaddr""",
        (mac,),
    ).fetchone()
    if device is None:
        raise HTTPException(404, "equipo inexistente")
    device["leases"] = conn.execute(
        """SELECT mac::text AS mac, host(ip) AS ip, hostname, vendor, client_id, lease_time, seen_at
           FROM current_leases WHERE cpe_mac = %s::macaddr ORDER BY ip""",
        (mac,),
    ).fetchall()
    device["stations"] = conn.execute(
        """SELECT mac::text AS mac, host(ip) AS ip, name, platform, signal, source, last_seen
           FROM devices WHERE ap_mac = %s::macaddr ORDER BY signal NULLS LAST""",
        (mac,),
    ).fetchall() if device["role"] == "ap" else []
    device["link_history"] = conn.execute(
        """SELECT l.seen_at, l.ap_mac::text AS ap_mac, l.signal, l.remote_signal, l.noisefloor,
                  l.dl_linkscore, l.ul_linkscore, l.uptime_s, l.distance_m
           FROM ap_links l WHERE l.cpe_mac = %s::macaddr ORDER BY l.seen_at DESC LIMIT 100""",
        (mac,),
    ).fetchall()
    return device


@api.get("/aps")
def list_aps(conn: Conn) -> list[dict]:
    return conn.execute(
        """SELECT ap.mac::text AS mac, host(ap.ip) AS ip, ap.name, ap.platform, ap.firmware, ap.ssid,
                  ap.last_seen, count(c.mac) AS stations,
                  min(c.signal) AS worst_signal, round(avg(c.signal))::int AS avg_signal
           FROM devices ap LEFT JOIN devices c ON c.ap_mac = ap.mac
           WHERE ap.role = 'ap'
           GROUP BY ap.mac
           ORDER BY ap.name"""
    ).fetchall()


@api.get("/leases/vendors")
def lease_vendors(conn: Conn) -> list[dict]:
    """Cuantos routers LAN hay de cada fabricante (para facetas de filtro)."""
    return conn.execute(
        """SELECT coalesce(vendor, '(desconocido)') AS vendor, count(*) AS leases,
                  count(*) FILTER (WHERE hostname ~ '^[0-9a-f]{20,}$') AS hostname_hash
           FROM current_leases GROUP BY 1 ORDER BY 2 DESC, 1"""
    ).fetchall()


@api.get("/leases")
def list_leases(
    conn: Conn,
    q: Annotated[str | None, Query(description="hostname, fabricante, MAC o IP del router LAN")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict]:
    return conn.execute(
        """SELECT cl.hostname, cl.vendor, cl.mac::text AS mac, host(cl.ip) AS ip, cl.client_id,
                  d.mac::text AS cpe_mac, d.name AS cpe_name, host(d.ip) AS cpe_ip, ap.name AS ap_name
           FROM current_leases cl
           JOIN devices d ON d.mac = cl.cpe_mac
           LEFT JOIN devices ap ON ap.mac = d.ap_mac
           WHERE %(q)s::text IS NULL OR concat_ws(' ', cl.hostname, cl.vendor, cl.mac::text, host(cl.ip)) ILIKE %(q)s
           ORDER BY cl.hostname NULLS LAST, d.name
           LIMIT %(limit)s""",
        {"q": _like(q), "limit": limit},
    ).fetchall()


# ---------- scans ----------

class ScanRequest(BaseModel):
    subnet_id: int | None = None


_SCAN_COLS = """s.id, s.subnet_id, n.cidr::text AS cidr, n.name AS subnet_name, s.status, s.trigger,
                s.requested_at, s.started_at, s.finished_at, s.hosts_alive, s.hosts_ok, s.hosts_failed, s.error"""


@api.get("/scans")
def list_scans(conn: Conn, limit: Annotated[int, Query(ge=1, le=200)] = 20) -> list[dict]:
    return conn.execute(
        f"SELECT {_SCAN_COLS} FROM scans s LEFT JOIN subnets n ON n.id = s.subnet_id ORDER BY s.id DESC LIMIT %s",
        (limit,),
    ).fetchall()


@api.get("/scans/{scan_id}")
def get_scan(scan_id: int, conn: Conn) -> dict:
    scan = conn.execute(
        f"SELECT {_SCAN_COLS} FROM scans s LEFT JOIN subnets n ON n.id = s.subnet_id WHERE s.id = %s", (scan_id,)
    ).fetchone()
    if scan is None:
        raise HTTPException(404, "escaneo inexistente")
    scan["errors"] = conn.execute(
        "SELECT host(host) AS host, error FROM scan_errors WHERE scan_id = %s ORDER BY host", (scan_id,)
    ).fetchall()
    return scan


@api.post("/scans", status_code=202)
def request_scan(body: ScanRequest, conn: Conn) -> dict:
    """Encola un escaneo de una subnet (o de todas las habilitadas). Lo ejecuta el worker."""
    if body.subnet_id is None:
        subnet_ids = [r["id"] for r in conn.execute("SELECT id FROM subnets WHERE enabled ORDER BY id")]
    elif conn.execute("SELECT 1 FROM subnets WHERE id = %s", (body.subnet_id,)).fetchone():
        subnet_ids = [body.subnet_id]
    else:
        raise HTTPException(404, "subnet inexistente")
    queued, already_active = [], []
    for sid in subnet_ids:
        scan_id = db.enqueue_scan(conn, sid, "manual")
        if scan_id is None:
            already_active.append(sid)
        else:
            queued.append(scan_id)
    return {"queued": queued, "already_active": already_active}


app.include_router(api)
