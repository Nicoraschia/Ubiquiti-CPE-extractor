"""Discovery: que IPs de una subnet tienen SSH abierto."""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor


def hosts_in(cidr: str) -> list[str]:
    return [str(ip) for ip in ipaddress.ip_network(cidr, strict=False).hosts()]


def port_open(host: str, port: int = 22, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def discover(cidr: str, workers: int = 128) -> list[str]:
    hosts = hosts_in(cidr)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [h for h, alive in zip(hosts, pool.map(port_open, hosts)) if alive]
