import argparse
import getpass
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .collector import collect


def _credentials() -> list[tuple[str, str]]:
    """SCAN_USER/SCAN_PASSWORD es la 1; SCAN_USER_2/SCAN_PASSWORD_2, la 2; y asi."""
    creds = []
    for suffix in ["", *(f"_{n}" for n in range(2, 10))]:
        user, password = os.environ.get(f"SCAN_USER{suffix}"), os.environ.get(f"SCAN_PASSWORD{suffix}")
        if user and password:
            creds.append((user, password))
    if not creds:
        creds.append((input("Usuario: "), getpass.getpass("Contraseña: ")))
    return creds


def _collect_all(hosts: list[str], workers: int, preferred: dict[str, int] | None = None):
    creds = _credentials()
    preferred = preferred or {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(lambda h: collect(h, creds, preferred.get(h)), hosts)


def cmd_probe(args) -> None:
    for result in _collect_all(args.hosts, args.workers):
        print(json.dumps(result, ensure_ascii=False))


def cmd_init_db(args) -> None:
    from . import db

    with db.connect() as conn:
        db.init_schema(conn)
    print("Esquema aplicado.")


def cmd_subnet_add(args) -> None:
    from . import db

    with db.connect() as conn:
        print(f"Subnet {args.cidr} -> id {db.add_subnet(conn, args.cidr, args.name)}")


def cmd_subnet_list(args) -> None:
    from . import db

    with db.connect() as conn:
        for sid, cidr, name, enabled in db.list_subnets(conn):
            print(f"{sid:>4}  {cidr:<18}  {'on ' if enabled else 'off'}  {name or ''}")


def cmd_scan(args) -> None:
    from . import db
    from .discovery import discover

    with db.connect() as conn:
        subnets = [s for s in db.list_subnets(conn, only_enabled=True) if args.subnet in (None, s[1])]
        if not subnets:
            sys.exit("No hay subnets para escanear. Agregalas con: cpe-scanner subnet add <cidr>")
        for sid, cidr, name, _ in subnets:
            t0 = time.monotonic()
            scan_id = db.start_scan(conn, sid)
            alive = discover(cidr)
            print(f"[scan {scan_id}] {cidr} ({name or '-'}): {len(alive)} hosts con SSH", flush=True)
            ok = failed = 0
            for r in _collect_all(alive, args.workers, db.cred_slots_by_ip(conn)):
                db.save_result(conn, scan_id, r)
                if r["ok"] and r.get("mac"):
                    ok += 1
                    extra = len(r.get("stations", r.get("leases", [])))
                    print(f"  ok   {r['host']:<16} {r['role']:<7} {r['name'] or ''} ({extra})", flush=True)
                else:
                    failed += 1
                    print(f"  fail {r['host']:<16} {r.get('error', 'sin MAC')}", flush=True)
            db.finish_scan(conn, scan_id, len(alive), ok, failed)
            print(f"[scan {scan_id}] ok={ok} fail={failed} en {time.monotonic() - t0:.1f}s")


def cmd_devices(args) -> None:
    from . import db

    with db.connect() as conn:
        rows = db.list_devices(conn, args.role, args.search)
    for mac, ip, role, name, platform, signal, source, ap_name in rows:
        print(f"{mac}  {ip or '-':<15} {role:<7} {signal if signal is not None else '':>4}  "
              f"{(name or '')[:28]:<28} {(platform or '')[:22]:<22} AP={ap_name or '-'} [{source}]")
    print(f"{len(rows)} equipos")


def main() -> None:
    p = argparse.ArgumentParser(prog="cpe-scanner")
    p.add_argument("-w", "--workers", type=int, default=30, help="conexiones SSH simultaneas")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("probe", help="escanea IPs y emite JSON (sin base de datos)")
    s.add_argument("hosts", nargs="+")
    s.set_defaults(func=cmd_probe)

    sub.add_parser("init-db", help="crea/actualiza el esquema").set_defaults(func=cmd_init_db)

    s = sub.add_parser("subnet", help="administra subnets")
    ssub = s.add_subparsers(dest="subcmd", required=True)
    a = ssub.add_parser("add")
    a.add_argument("cidr")
    a.add_argument("--name")
    a.set_defaults(func=cmd_subnet_add)
    ssub.add_parser("list").set_defaults(func=cmd_subnet_list)

    s = sub.add_parser("scan", help="discovery + recoleccion de las subnets habilitadas")
    s.add_argument("--subnet", help="solo esta subnet (CIDR exacto)")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("devices", help="lista equipos guardados")
    s.add_argument("--role", choices=["ap", "cpe", "unknown"])
    s.add_argument("-q", "--search", help="busca en nombre, modelo, MAC, IP, SSID")
    s.set_defaults(func=cmd_devices)

    args = p.parse_args()
    args.func(args)
