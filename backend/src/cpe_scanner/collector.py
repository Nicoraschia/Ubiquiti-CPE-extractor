"""Conexion SSH a un equipo airOS y recoleccion segun su rol."""

from dataclasses import asdict

import paramiko

from .parsers import (
    classify_role,
    parse_dhcpd_leases,
    parse_mca_status,
    parse_system_cfg,
    parse_wstalist,
)

# Claves de system.cfg que interesan al inventario; el resto se descarta.
CFG_KEYS = (
    "resolv.host.1.name",
    "wireless.1.ssid",
    "radio.1.mode",
    "radio.1.freq",
    "netmode",
    "tshaper.status",
    "tshaper.1.input.rate",
    "tshaper.1.output.rate",
)


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float) -> str:
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace")


def collect(host: str, username: str, password: str, timeout: float = 10) -> dict:
    """Devuelve {'host', 'ok', ...}. Nunca lanza por errores de red o SSH."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            host,
            username=username,
            password=password,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        mca = parse_mca_status(_run(ssh, "mca-status", timeout))
        cfg = parse_system_cfg(_run(ssh, "cat /tmp/system.cfg", timeout))
        role = classify_role(mca, cfg)
        result = {
            "host": host,
            "ok": True,
            "role": role,
            "mac": mca.get("deviceId", "").lower() or None,
            "name": mca.get("deviceName"),
            "platform": mca.get("platform"),
            "firmware": mca.get("firmwareVersion"),
            "ap_mac": mca.get("apMac", "").lower() or None,
            "signal": mca.get("signal"),
            "config": {k: cfg[k] for k in CFG_KEYS if k in cfg},
        }
        if role == "ap":
            result["stations"] = [asdict(s) for s in parse_wstalist(_run(ssh, "wstalist", timeout))]
        elif role == "cpe":
            leases = parse_dhcpd_leases(_run(ssh, "cat /var/tmp/dhcpd.leases", timeout))
            result["leases"] = [asdict(l) for l in leases]
        return result
    # OSError cubre timeouts y conexiones rechazadas; SSHException cubre auth y negociacion.
    except (paramiko.SSHException, OSError) as e:
        return {"host": host, "ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        ssh.close()
