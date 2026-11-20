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


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _mac(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value or None


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
        # MAC de la interfaz wireless: la misma que el AP muestra en wstalist y que el
        # CPE reporta como apMac. Es la clave del equipo en la base.
        wlan_dev = cfg.get("wireless.1.devname", "ath0")
        wlan_mac = _mac(_run(ssh, f"cat /sys/class/net/{wlan_dev}/address", timeout))
        result = {
            "host": host,
            "ok": True,
            "role": role,
            "mac": wlan_mac or _mac(mca.get("deviceId")),
            "device_id": _mac(mca.get("deviceId")),
            "name": mca.get("deviceName"),
            "platform": mca.get("platform"),
            "firmware": mca.get("firmwareVersion"),
            # En un AP, apMac es su propia MAC: no es un vinculo.
            "ap_mac": _mac(mca.get("apMac")) if role == "cpe" else None,
            "signal": _int(mca.get("signal")),
            "ssid": cfg.get("wireless.1.ssid"),
            "netmode": cfg.get("netmode"),
            "shaper_in": _int(cfg.get("tshaper.1.input.rate")) if cfg.get("tshaper.status") == "enabled" else None,
            "shaper_out": _int(cfg.get("tshaper.1.output.rate")) if cfg.get("tshaper.status") == "enabled" else None,
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
