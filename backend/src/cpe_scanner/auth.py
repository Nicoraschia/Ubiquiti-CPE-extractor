"""Usuarios, sesiones y freno de fuerza bruta. Todo el estado vive en Postgres."""

import hashlib
import re
import secrets
from dataclasses import dataclass

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb

ROLES = ("admin", "viewer")
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
PASSWORD_MIN, PASSWORD_MAX = 12, 128  # el maximo evita gastar CPU de Argon2 con entradas enormes

SESSION_IDLE = "60 minutes"   # sin actividad: hay que volver a entrar
SESSION_MAX = "12 hours"      # un turno; despues se pide login aunque haya actividad
FAIL_WINDOW = "15 minutes"
FAILS_PER_USER = 5
FAILS_PER_IP = 20

_ph = PasswordHasher()  # Argon2id, parametros RFC 9106 (64 MiB, t=3)
# Se verifica contra este hash si el usuario no existe: misma demora, no delata cuales existen.
_DUMMY_HASH = _ph.hash(secrets.token_hex(16))


@dataclass(frozen=True)
class Principal:
    id: int | None  # None = API_TOKEN (scripts)
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class LoginThrottled(Exception):
    pass


class PasswordPolicyError(ValueError):
    pass


def _cur(conn: psycopg.Connection) -> psycopg.Cursor:
    return conn.cursor(row_factory=tuple_row)


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def check_password_policy(username: str, password: str) -> None:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise PasswordPolicyError(f"la clave debe tener entre {PASSWORD_MIN} y {PASSWORD_MAX} caracteres")
    if username.lower() in password.lower():
        raise PasswordPolicyError("la clave no puede contener el nombre de usuario")


def normalize_username(username: str) -> str:
    u = username.strip().lower()
    if not USERNAME_RE.match(u):
        raise ValueError("usuario: 3 a 32 caracteres a-z, 0-9, punto, guion o guion bajo")
    return u


def create_user(conn: psycopg.Connection, username: str, password: str, role: str) -> int:
    username = normalize_username(username)
    if role not in ROLES:
        raise ValueError(f"rol invalido: {role}")
    check_password_policy(username, password)
    row = _cur(conn).execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING id",
        (username, _ph.hash(password), role),
    ).fetchone()
    conn.commit()
    return row[0]


def set_password(conn: psycopg.Connection, user_id: int, password: str, keep_session: str | None = None) -> None:
    """Cambia la clave y cierra las demas sesiones del usuario (salvo la actual, si se pasa)."""
    (username,) = _cur(conn).execute("SELECT username FROM users WHERE id = %s", (user_id,)).fetchone()
    check_password_policy(username, password)
    conn.execute(
        "UPDATE users SET password_hash = %s, password_changed_at = now() WHERE id = %s",
        (_ph.hash(password), user_id),
    )
    keep = _token_hash(keep_session) if keep_session else None
    conn.execute(
        "DELETE FROM sessions WHERE user_id = %s AND token_hash IS DISTINCT FROM %s", (user_id, keep)
    )
    conn.commit()


def verify_password(conn: psycopg.Connection, user_id: int, password: str) -> bool:
    (h,) = _cur(conn).execute("SELECT password_hash FROM users WHERE id = %s", (user_id,)).fetchone()
    try:
        return _ph.verify(h, password[:PASSWORD_MAX])
    except (VerifyMismatchError, InvalidHashError):
        return False


def revoke_sessions(conn: psycopg.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
    conn.commit()


def _throttled(conn: psycopg.Connection, username: str, ip: str | None) -> bool:
    per_user, per_ip = _cur(conn).execute(
        f"""SELECT count(*) FILTER (WHERE username = %s),
                   count(*) FILTER (WHERE ip = %s::inet)
            FROM login_failures WHERE at > now() - interval '{FAIL_WINDOW}'""",
        (username, ip),
    ).fetchone()
    return per_user >= FAILS_PER_USER or per_ip >= FAILS_PER_IP


def login(conn: psycopg.Connection, username: str, password: str, ip: str | None,
          user_agent: str | None) -> tuple[str, Principal] | None:
    """Devuelve (token, usuario) o None. LoginThrottled si hay demasiados intentos fallidos."""
    username = username.strip().lower()[:64]
    if _throttled(conn, username, ip):
        audit(conn, None, username or "?", "login_throttled", None, ip)
        raise LoginThrottled
    row = _cur(conn).execute(
        "SELECT id, password_hash, role FROM users WHERE username = %s AND enabled", (username,)
    ).fetchone()
    try:
        ok = _ph.verify(row[1] if row else _DUMMY_HASH, password[:PASSWORD_MAX]) and row is not None
    except (VerifyMismatchError, InvalidHashError):
        ok = False
    if not ok:
        conn.execute("INSERT INTO login_failures (username, ip) VALUES (%s, %s)", (username, ip))
        audit(conn, None, username or "?", "login_failed", None, ip)
        return None

    user_id, pw_hash, role = row
    if _ph.check_needs_rehash(pw_hash):
        conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (_ph.hash(password), user_id))
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, ip, user_agent) VALUES (%s, %s, %s, %s)",
        (_token_hash(token), user_id, ip, (user_agent or "")[:256]),
    )
    conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user_id,))
    conn.execute("DELETE FROM login_failures WHERE username = %s OR at < now() - interval '1 day'", (username,))
    principal = Principal(user_id, username, role)
    audit(conn, principal, username, "login", None, ip)
    return token, principal


def session_principal(conn: psycopg.Connection, token: str) -> Principal | None:
    """Usuario de una sesion vigente; renueva su actividad (vence por inactividad o por duracion)."""
    row = _cur(conn).execute(
        f"""UPDATE sessions s SET last_seen_at = now()
            FROM users u
            WHERE s.token_hash = %s AND u.id = s.user_id AND u.enabled
              AND s.created_at > now() - interval '{SESSION_MAX}'
              AND s.last_seen_at > now() - interval '{SESSION_IDLE}'
            RETURNING u.id, u.username, u.role""",
        (_token_hash(token),),
    ).fetchone()
    conn.commit()
    return Principal(*row) if row else None


def logout(conn: psycopg.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = %s", (_token_hash(token),))
    conn.execute(
        f"""DELETE FROM sessions WHERE created_at < now() - interval '{SESSION_MAX}'
                                    OR last_seen_at < now() - interval '{SESSION_IDLE}'"""
    )
    conn.commit()


def audit(conn: psycopg.Connection, who: Principal | None, actor: str, action: str,
          detail: dict | None, ip: str | None) -> None:
    conn.execute(
        "INSERT INTO audit_log (user_id, actor, action, detail, ip) VALUES (%s, %s, %s, %s, %s)",
        (who.id if who else None, actor, action, Jsonb(detail) if detail else None, ip),
    )
    conn.commit()
