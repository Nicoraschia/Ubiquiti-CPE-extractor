"""Conexion SSH a un equipo airOS y recoleccion segun su rol."""

import base64
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


Credential = tuple[str, str]
HostKey = tuple[str, str]  # (tipo, base64), p. ej. ("ssh-rsa", "AAAAB3...")

HOST_KEY_CHANGED = (
    "host key distinta a la registrada: no se enviaron credenciales. Posible suplantacion o "
    "equipo reemplazado; si es legitimo, olvidar la clave registrada de esta IP"
)


def _pkey(keytype: str, b64: str) -> paramiko.PKey:
    return paramiko.PKey.from_type_string(keytype, base64.b64decode(b64))


def _server_key(ssh: paramiko.SSHClient) -> HostKey:
    key = ssh.get_transport().get_remote_server_key()
    return key.get_name(), key.get_base64()


class _TrustOnFirstUse(paramiko.MissingHostKeyPolicy):
    """Equipo nunca visto: se acepta y el escaneo guarda su clave. Desde ahi queda fijada."""

    def missing_host_key(self, client, hostname, key):
        pass


def _connect(
    host: str, creds: list[Credential], first: int | None, timeout: float, known: HostKey | None = None
) -> tuple[paramiko.SSHClient, int]:
    """Prueba las credenciales en orden (empezando por `first`, la que funciono antes).

    Devuelve (cliente, slot 1-based). Solo un fallo de autenticacion pasa a la siguiente;
    timeouts o conexion rechazada cortan, porque otra clave no los arregla.

    Con `known`, paramiko compara la host key en el intercambio de claves, antes de autenticar:
    si no coincide lanza BadHostKeyException y ninguna contrasena sale hacia ese host.
    """
    order = list(range(len(creds)))
    if first is not None and 1 <= first <= len(creds):
        order.remove(first - 1)
        order.insert(0, first - 1)
    for i in order:
        # Cliente nuevo por intento: dropbear corta la sesion tras un auth fallido.
        ssh = paramiko.SSHClient()
        if known is not None:
            ssh.get_host_keys().add(host, known[0], _pkey(*known))
        ssh.set_missing_host_key_policy(_TrustOnFirstUse())
        try:
            ssh.connect(
                host,
                username=creds[i][0],
                password=creds[i][1],
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            return ssh, i + 1
        except paramiko.AuthenticationException:
            ssh.close()
        except BaseException:
            ssh.close()
            raise
    raise paramiko.AuthenticationException(f"ninguna credencial funciono ({len(creds)} probadas)")


def collect(
    host: str, creds: list[Credential], first: int | None = None, timeout: float = 10, known: HostKey | None = None
) -> dict:
    """Devuelve {'host', 'ok', ...}. Nunca lanza por errores de red o SSH."""
    ssh = None
    try:
        ssh, slot = _connect(host, creds, first, timeout, known)
        host_key = _server_key(ssh)
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
            "cred_slot": slot,
            "host_key": host_key,
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
    except paramiko.BadHostKeyException:
        return {"host": host, "ok": False, "error": HOST_KEY_CHANGED}
    # OSError cubre timeouts y conexiones rechazadas; SSHException cubre auth y negociacion.
    except (paramiko.SSHException, OSError) as e:
        return {"host": host, "ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        if ssh is not None:
            ssh.close()
