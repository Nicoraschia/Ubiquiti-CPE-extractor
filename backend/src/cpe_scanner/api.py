"""API HTTP del inventario. La consume la web (BFF Next.js) con token de sesion y scripts con API_TOKEN.

Lectura: cualquier usuario. Escritura (subnets, escaneos, usuarios): solo admin.
"""

import ipaddress
import os
import secrets
from collections.abc import Iterator
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

from . import auth, db
from .auth import Principal

MAC_RE = r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"


def get_conn() -> Iterator[psycopg.Connection]:
    with db.connect() as conn:
        conn.row_factory = dict_row
        yield conn


# Esquema de seguridad declarado: /docs muestra el boton Authorize y manda el header.
# (Swagger UI ignora un parametro de header llamado Authorization.)
bearer = HTTPBearer(auto_error=False, description="Token de sesion (login) o API_TOKEN del .env")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Creds = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def client_ip(request: Request) -> str | None:
    # La API solo es alcanzable desde la red interna de docker y localhost: el BFF pasa la IP real.
    ip = request.headers.get("x-client-ip") or (request.client.host if request.client else None)
    try:
        return str(ipaddress.ip_address(ip)) if ip else None
    except ValueError:
        return None


def current_user(creds: Creds, conn: Conn) -> Principal:
    if creds is not None:
        api_token = os.environ.get("API_TOKEN")
        if api_token and secrets.compare_digest(creds.credentials.encode(), api_token.encode()):
            return Principal(None, "api-token", "admin")
        if user := auth.session_principal(conn, creds.credentials):
            return user
    raise HTTPException(401, "sesion invalida o vencida", headers={"WWW-Authenticate": "Bearer"})


User = Annotated[Principal, Depends(current_user)]


def require_admin(user: User) -> Principal:
    if not user.is_admin:
        raise HTTPException(403, "requiere rol admin")
    return user


Admin = Annotated[Principal, Depends(require_admin)]

app = FastAPI(title="CPE Scanner API", version="0.3.0")
api = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


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
def create_subnet(body: SubnetIn, conn: Conn, user: Admin, request: Request) -> dict:
    sid = db.add_subnet(conn, body.cidr, body.name)
    auth.audit(conn, user, user.username, "subnet_add", {"cidr": body.cidr, "name": body.name}, client_ip(request))
    return conn.execute(f"SELECT {_SUBNET_COLS} FROM subnets WHERE id = %s", (sid,)).fetchone()


@api.patch("/subnets/{subnet_id}")
def update_subnet(subnet_id: int, body: SubnetPatch, conn: Conn, user: Admin, request: Request) -> dict:
    row = conn.execute(
        f"""UPDATE subnets SET name = COALESCE(%s, name), enabled = COALESCE(%s, enabled)
            WHERE id = %s RETURNING {_SUBNET_COLS}""",
        (body.name, body.enabled, subnet_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "subnet inexistente")
    conn.commit()
    auth.audit(conn, user, user.username, "subnet_update",
               {"id": subnet_id, **body.model_dump(exclude_none=True)}, client_ip(request))
    return row


# ---------- devices ----------

def _like(v: str | None) -> str | None:
    # '_' y '%' son comodines de LIKE: "AP_TEST" no debe matchear "AP-TEST".
    if not v:
        return None
    return "%" + v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _terms(v: str | None) -> list[str] | None:
    """Busqueda por palabras: "huawei 192.168.18." exige que esten TODAS (en cualquier campo)."""
    terms = [_like(t) for t in (v or "").split()]
    return terms or None


def _all_match(haystack: str, param: str) -> str:
    # Ningun termino sin matchear = todos matchean. NULL = sin filtro.
    return (f"(%({param})s::text[] IS NULL OR NOT EXISTS ("
            f"SELECT 1 FROM unnest(%({param})s::text[]) t WHERE NOT ({haystack} ILIKE t)))")


_SORTS = {
    "name": "d.name", "signal": "d.signal", "ip": "d.ip", "platform": "d.platform",
    "last_seen": "d.last_seen", "ap": "ap.name",
}

_DEVICE_FILTERS = f"""
FROM devices d LEFT JOIN devices ap ON ap.mac = d.ap_mac
WHERE (%(role)s::text IS NULL OR d.role = %(role)s)
  AND (%(ap)s::macaddr IS NULL OR d.ap_mac = %(ap)s::macaddr)
  AND (%(platform)s::text IS NULL OR d.platform ILIKE %(platform)s)
  AND (%(source)s::text IS NULL OR d.source = %(source)s)
  AND (%(signal_max)s::int IS NULL OR d.signal <= %(signal_max)s)
  AND {_all_match("concat_ws(' ', d.name, d.platform, d.firmware, d.mac::text, host(d.ip), d.ssid, ap.name)", "q")}
  AND (%(lan)s::text[] IS NULL OR EXISTS (
        SELECT 1 FROM current_leases cl
        WHERE cl.cpe_mac = d.mac
          AND {_all_match("concat_ws(' ', cl.hostname, cl.vendor, cl.mac::text, host(cl.ip))", "lan")}))
"""


@api.get("/devices")
def list_devices(
    conn: Conn,
    q: Annotated[str | None, Query(description="palabras (todas deben estar): nombre, modelo, firmware, MAC, IP, SSID o AP")] = None,
    role: Literal["ap", "cpe", "unknown"] | None = None,
    ap: Annotated[str | None, Query(pattern=MAC_RE, description="MAC del AP")] = None,
    platform: str | None = None,
    lan: Annotated[str | None, Query(description="router LAN, palabras (todas en el mismo lease): hostname, fabricante, MAC o IP")] = None,
    source: Literal["ssh", "wstalist"] | None = None,
    signal_max: Annotated[int | None, Query(description="senal <= este valor (ej. -70)")] = None,
    sort: Literal["name", "signal", "ip", "platform", "last_seen", "ap"] = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    params = {
        "q": _terms(q), "role": role, "ap": ap, "platform": _like(platform), "lan": _terms(lan),
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
    q: Annotated[str | None, Query(
        description="palabras (todas deben estar): hostname, fabricante, MAC o IP del router; nombre o IP del CPE; AP"
    )] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict]:
    haystack = ("concat_ws(' ', cl.hostname, cl.vendor, cl.mac::text, host(cl.ip), "
                "d.name, host(d.ip), ap.name)")
    return conn.execute(
        f"""SELECT cl.hostname, cl.vendor, cl.mac::text AS mac, host(cl.ip) AS ip, cl.client_id,
                   d.mac::text AS cpe_mac, d.name AS cpe_name, host(d.ip) AS cpe_ip, ap.name AS ap_name
            FROM current_leases cl
            JOIN devices d ON d.mac = cl.cpe_mac
            LEFT JOIN devices ap ON ap.mac = d.ap_mac
            WHERE {_all_match(haystack, "q")}
            ORDER BY cl.hostname NULLS LAST, d.name
            LIMIT %(limit)s""",
        {"q": _terms(q), "limit": limit},
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
def request_scan(body: ScanRequest, conn: Conn, user: Admin, request: Request) -> dict:
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
    auth.audit(conn, user, user.username, "scan_request", {"subnet_id": body.subnet_id, "queued": queued},
               client_ip(request))
    return {"queued": queued, "already_active": already_active}


# ---------- auth ----------

class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=auth.PASSWORD_MAX)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=auth.PASSWORD_MAX)
    new_password: str = Field(max_length=auth.PASSWORD_MAX)


def _me(user: Principal) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role}


public = APIRouter(prefix="/api/auth")


@public.post("/login")
def login(body: LoginIn, conn: Conn, request: Request) -> dict:
    """Devuelve un token de sesion opaco. El BFF lo guarda en una cookie httpOnly; el navegador nunca lo ve."""
    try:
        result = auth.login(conn, body.username, body.password, client_ip(request),
                            request.headers.get("user-agent"))
    except auth.LoginThrottled:
        raise HTTPException(429, "demasiados intentos fallidos, espera 15 minutos") from None
    if result is None:
        raise HTTPException(401, "usuario o clave incorrectos")
    token, user = result
    return {"token": token, "user": _me(user)}


@api.get("/auth/me")
def me(user: User) -> dict:
    return _me(user)


@api.post("/auth/logout", status_code=204)
def logout(creds: Creds, conn: Conn, user: User, request: Request) -> None:
    auth.logout(conn, creds.credentials)
    auth.audit(conn, user, user.username, "logout", None, client_ip(request))


@api.post("/auth/password", status_code=204)
def change_password(body: PasswordChange, creds: Creds, conn: Conn, user: User, request: Request) -> None:
    if user.id is None:
        raise HTTPException(400, "API_TOKEN no tiene clave: se cambia en el .env")
    if not auth.verify_password(conn, user.id, body.current_password):
        raise HTTPException(400, "la clave actual no es correcta")
    try:
        auth.set_password(conn, user.id, body.new_password, keep_session=creds.credentials)
    except auth.PasswordPolicyError as e:
        raise HTTPException(422, str(e)) from None
    auth.audit(conn, user, user.username, "password_change", None, client_ip(request))


# ---------- usuarios (admin) ----------

class UserIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=auth.PASSWORD_MAX)
    role: Literal["admin", "viewer"] = "viewer"


class UserPatch(BaseModel):
    role: Literal["admin", "viewer"] | None = None
    enabled: bool | None = None
    password: str | None = Field(default=None, max_length=auth.PASSWORD_MAX)


_USER_COLS = """u.id, u.username, u.role, u.enabled, u.created_at, u.last_login_at, u.password_changed_at,
                (SELECT count(*) FROM sessions s WHERE s.user_id = u.id) AS sessions"""


def _get_user(conn: psycopg.Connection, user_id: int) -> dict:
    row = conn.execute(f"SELECT {_USER_COLS} FROM users u WHERE u.id = %s", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "usuario inexistente")
    return row


@api.get("/users", dependencies=[Depends(require_admin)])
def list_users(conn: Conn) -> list[dict]:
    return conn.execute(f"SELECT {_USER_COLS} FROM users u ORDER BY u.username").fetchall()


@api.post("/users", status_code=201)
def create_user(body: UserIn, conn: Conn, user: Admin, request: Request) -> dict:
    try:
        uid = auth.create_user(conn, body.username, body.password, body.role)
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(409, "ese usuario ya existe") from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    auth.audit(conn, user, user.username, "user_add", {"id": uid, "role": body.role}, client_ip(request))
    return _get_user(conn, uid)


@api.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, conn: Conn, user: Admin, request: Request) -> dict:
    _get_user(conn, user_id)
    # Un admin no puede quitarse el acceso a si mismo: siempre queda al menos uno.
    if user_id == user.id and (body.enabled is False or body.role == "viewer"):
        raise HTTPException(400, "no podes desactivarte ni quitarte el rol admin a vos mismo")
    if body.password is not None:
        try:
            auth.set_password(conn, user_id, body.password)
        except auth.PasswordPolicyError as e:
            raise HTTPException(422, str(e)) from None
    conn.execute(
        "UPDATE users SET role = COALESCE(%s, role), enabled = COALESCE(%s, enabled) WHERE id = %s",
        (body.role, body.enabled, user_id),
    )
    conn.commit()
    if body.enabled is False or body.role is not None:
        auth.revoke_sessions(conn, user_id)  # el cambio de permisos rige ya, no al vencer la sesion
    changes = body.model_dump(exclude_none=True, exclude={"password"})
    if body.password is not None:
        changes["password_reset"] = True
    auth.audit(conn, user, user.username, "user_update", {"id": user_id, **changes}, client_ip(request))
    return _get_user(conn, user_id)


@api.get("/audit", dependencies=[Depends(require_admin)])
def audit_log(conn: Conn, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict]:
    return conn.execute(
        "SELECT id, at, actor, action, detail, host(ip) AS ip FROM audit_log ORDER BY id DESC LIMIT %s", (limit,)
    ).fetchall()


app.include_router(public)
app.include_router(api)
