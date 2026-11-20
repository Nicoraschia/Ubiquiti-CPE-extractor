import argparse
import getpass
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from .collector import collect


def main() -> None:
    p = argparse.ArgumentParser(prog="cpe-scanner", description="Escanea equipos airOS por SSH y emite JSON por linea.")
    p.add_argument("hosts", nargs="*", help="IPs a escanear (o usar --file)")
    p.add_argument("-f", "--file", help="archivo con una IP por linea")
    p.add_argument("-u", "--user", default="ubnt")
    p.add_argument("-w", "--workers", type=int, default=20)
    args = p.parse_args()

    hosts = list(args.hosts)
    if args.file:
        with open(args.file) as fh:
            hosts += [line.strip() for line in fh if line.strip()]
    if not hosts:
        p.error("no hay hosts")

    password = getpass.getpass("Contraseña: ")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda h: collect(h, args.user, password), hosts):
            print(json.dumps(result, ensure_ascii=False))
            if not result["ok"]:
                print(f"[error] {result['host']}: {result['error']}", file=sys.stderr)
