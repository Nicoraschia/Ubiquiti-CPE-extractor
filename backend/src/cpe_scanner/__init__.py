import argparse
import json
import sys
import time


def cmd_probe(args) -> None:
    from .scanner import collect_all, credentials

    for result in collect_all(args.hosts, credentials(interactive=True), args.workers):
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


def _print_result(r: dict) -> None:
    if r["ok"] and r.get("mac"):
        extra = len(r.get("stations", r.get("leases", [])))
        print(f"  ok   {r['host']:<16} {r['role']:<7} {r['name'] or ''} ({extra})", flush=True)
    else:
        print(f"  fail {r['host']:<16} {r.get('error', 'sin MAC')}", flush=True)


def cmd_scan(args) -> None:
    from . import db
    from .scanner import credentials, run_scan

    with db.connect() as conn:
        subnets = [s for s in db.list_subnets(conn, only_enabled=True) if args.subnet in (None, s[1])]
        if not subnets:
            sys.exit("No hay subnets para escanear. Agregalas con: cpe-scanner subnet add <cidr>")
        creds = credentials(interactive=True)
        for sid, cidr, name, _ in subnets:
            scan_id = db.start_scan(conn, sid)
            if scan_id is None:
                print(f"{cidr}: ya hay un escaneo pendiente o en curso, se saltea.")
                continue
            t0 = time.monotonic()
            print(f"[scan {scan_id}] {cidr} ({name or '-'})", flush=True)
            try:
                alive, ok, failed = run_scan(conn, scan_id, cidr, creds, args.workers, _print_result)
            except BaseException as e:
                # Incluye Ctrl+C: el scan no puede quedar 'running' bloqueando la subnet.
                conn.rollback()
                db.finish_scan(conn, scan_id, None, None, None, status="failed", error=repr(e))
                raise
            db.finish_scan(conn, scan_id, alive, ok, failed)
            print(f"[scan {scan_id}] {alive} hosts con SSH, ok={ok} fail={failed} en {time.monotonic() - t0:.1f}s")


def cmd_oui_update(args) -> None:
    from . import db, oui

    with db.connect() as conn:
        print(f"{oui.replace_vendors(conn, oui.download())} fabricantes cargados.")


def _ask_password() -> str:
    import getpass

    pw = getpass.getpass("Clave nueva: ")
    if pw != getpass.getpass("Repetir clave: "):
        sys.exit("Las claves no coinciden.")
    return pw


def cmd_user_add(args) -> None:
    from . import auth, db

    with db.connect() as conn:
        try:
            uid = auth.create_user(conn, args.username, _ask_password(), args.role)
        except ValueError as e:
            sys.exit(str(e))
        auth.audit(conn, None, "cli", "user_add", {"id": uid, "role": args.role}, None)
    print(f"Usuario {args.username} ({args.role}) -> id {uid}")


def cmd_user_passwd(args) -> None:
    from . import auth, db

    with db.connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = %s", (args.username.lower(),)).fetchone()
        if row is None:
            sys.exit(f"No existe el usuario {args.username}")
        try:
            auth.set_password(conn, row[0], _ask_password())
        except ValueError as e:
            sys.exit(str(e))
        # Tambien reactiva: es la salida si un admin quedo desactivado.
        conn.execute("UPDATE users SET enabled = true WHERE id = %s", (row[0],))
        conn.commit()
        auth.audit(conn, None, "cli", "user_update", {"id": row[0], "password_reset": True}, None)
    print("Clave cambiada; sus sesiones abiertas se cerraron.")


def cmd_user_list(args) -> None:
    from . import db

    with db.connect() as conn:
        rows = conn.execute("SELECT username, role, enabled, last_login_at FROM users ORDER BY username").fetchall()
    for username, role, enabled, last in rows:
        print(f"{username:<24} {role:<7} {'on ' if enabled else 'off'}  ultimo login: {last or '-'}")


def cmd_worker(args) -> None:
    from .worker import run

    run(args.workers)


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

    s = sub.add_parser("oui", help="lista de fabricantes por MAC (IEEE)")
    osub = s.add_subparsers(dest="subcmd", required=True)
    osub.add_parser("update", help="descarga y reemplaza la lista").set_defaults(func=cmd_oui_update)

    s = sub.add_parser("user", help="usuarios de la web")
    usub = s.add_subparsers(dest="subcmd", required=True)
    a = usub.add_parser("add", help="crea un usuario (pide la clave)")
    a.add_argument("username")
    a.add_argument("--role", choices=["admin", "viewer"], default="viewer")
    a.set_defaults(func=cmd_user_add)
    a = usub.add_parser("passwd", help="cambia la clave y reactiva el usuario")
    a.add_argument("username")
    a.set_defaults(func=cmd_user_passwd)
    usub.add_parser("list").set_defaults(func=cmd_user_list)

    sub.add_parser("worker", help="procesa la cola de escaneos y los programa").set_defaults(func=cmd_worker)

    s = sub.add_parser("devices", help="lista equipos guardados")
    s.add_argument("--role", choices=["ap", "cpe", "unknown"])
    s.add_argument("-q", "--search", help="busca en nombre, modelo, MAC, IP, SSID")
    s.set_defaults(func=cmd_devices)

    args = p.parse_args()
    args.func(args)
