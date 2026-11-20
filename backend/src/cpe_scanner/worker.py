"""Worker: programa escaneos periodicos y procesa la cola (tabla scans)."""

import logging
import os
import time

import psycopg

from . import db
from .collector import Credential
from .scanner import NoCredentials, credentials, run_scan

log = logging.getLogger("cpe_scanner.worker")
POLL_S = 5


def schedule_all(conn: psycopg.Connection) -> list[int]:
    """Encola un escaneo por cada subnet habilitada que no tenga uno activo."""
    queued = []
    for sid, cidr, _, _ in db.list_subnets(conn, only_enabled=True):
        scan_id = db.enqueue_scan(conn, sid, "schedule")
        if scan_id is not None:
            queued.append(scan_id)
            log.info("programado scan %s para %s", scan_id, cidr)
    return queued


def process_one(conn: psycopg.Connection, creds: list[Credential] | None, workers: int) -> bool:
    """Procesa un escaneo pendiente. Devuelve False si la cola estaba vacia."""
    job = db.claim_scan(conn)
    if job is None:
        return False
    scan_id, _, cidr, name = job
    t0 = time.monotonic()
    log.info("scan %s: %s (%s)", scan_id, cidr, name or "-")
    try:
        if creds is None:
            raise NoCredentials("faltan SCAN_USER/SCAN_PASSWORD en el .env")
        alive, ok, failed = run_scan(conn, scan_id, cidr, creds, workers)
    except Exception as e:
        # Un escaneo roto se registra como failed y el worker sigue con la cola.
        conn.rollback()
        db.finish_scan(conn, scan_id, None, None, None, status="failed", error=f"{type(e).__name__}: {e}")
        log.exception("scan %s fallo", scan_id)
        return True
    db.finish_scan(conn, scan_id, alive, ok, failed)
    log.info("scan %s: %s hosts, ok=%s fail=%s en %.1fs", scan_id, alive, ok, failed, time.monotonic() - t0)
    return True


def run(workers: int) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # paramiko loguea cada login en INFO: con cientos de equipos tapa el log del worker.
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    # 0 desactiva el programado: solo se procesan escaneos pedidos por API o CLI.
    interval_s = int(os.environ.get("SCAN_INTERVAL_MIN", "60")) * 60
    try:
        creds = credentials(interactive=False)
    except NoCredentials as e:
        log.error("%s: los escaneos van a fallar hasta configurarlas", e)
        creds = None

    with db.connect() as conn:
        db.init_schema(conn)
        if stale := db.fail_stale_scans(conn):
            log.warning("%s escaneos colgados marcados como failed", stale)
        next_schedule = time.monotonic()  # el primero, al arrancar
        log.info("worker listo: intervalo=%s min, %s credenciales", interval_s // 60, len(creds or []))
        while True:
            if interval_s and time.monotonic() >= next_schedule:
                schedule_all(conn)
                next_schedule = time.monotonic() + interval_s
            if not process_one(conn, creds, workers):
                time.sleep(POLL_S)
