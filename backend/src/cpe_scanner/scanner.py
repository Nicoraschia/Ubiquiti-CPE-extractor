"""Escaneo de una subnet: discovery + recoleccion + persistencia. Lo usan el CLI y el worker."""

import getpass
import os
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor

import psycopg

from . import db
from .collector import Credential, HostKey, collect
from .discovery import discover


class NoCredentials(RuntimeError):
    pass


def credentials(interactive: bool) -> list[Credential]:
    """SCAN_USER/SCAN_PASSWORD es la 1; SCAN_USER_2/SCAN_PASSWORD_2, la 2; y asi."""
    creds = []
    for suffix in ["", *(f"_{n}" for n in range(2, 10))]:
        user, password = os.environ.get(f"SCAN_USER{suffix}"), os.environ.get(f"SCAN_PASSWORD{suffix}")
        if user and password:
            creds.append((user, password))
    if not creds:
        if not interactive:
            raise NoCredentials("faltan SCAN_USER/SCAN_PASSWORD en el .env")
        creds.append((input("Usuario: "), getpass.getpass("Contraseña: ")))
    return creds


def collect_all(
    hosts: list[str],
    creds: list[Credential],
    workers: int,
    preferred: dict[str, int] | None = None,
    known_keys: dict[str, HostKey] | None = None,
) -> Iterator[dict]:
    preferred, known_keys = preferred or {}, known_keys or {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(lambda h: collect(h, creds, preferred.get(h), known=known_keys.get(h)), hosts)


def run_scan(
    conn: psycopg.Connection,
    scan_id: int,
    cidr: str,
    creds: list[Credential],
    workers: int,
    on_result: Callable[[dict], None] = lambda r: None,
) -> tuple[int, int, int]:
    """Escanea y guarda. Devuelve (alive, ok, failed); no marca el scan como terminado."""
    alive = discover(cidr)
    ok = failed = 0
    for r in collect_all(alive, creds, workers, db.cred_slots_by_ip(conn), db.host_keys(conn)):
        db.save_result(conn, scan_id, r)
        if r["ok"] and r.get("mac"):
            ok += 1
        else:
            failed += 1
        on_result(r)
    return len(alive), ok, failed
