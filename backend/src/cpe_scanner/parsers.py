"""Parsers puros para salidas de airOS. Sin SSH: reciben texto, devuelven datos."""

import json
import re
from dataclasses import dataclass
from typing import Literal

Role = Literal["ap", "cpe", "unknown"]

# Claves de system.cfg que nunca deben salir del parser (credenciales/tokens).
_SECRET_KEY = re.compile(r"(psk|password|passwd|secret|\.key\b|unms\.uri|community)", re.I)
_MCA_SPLIT = re.compile(r",(?=\w+=)")
_CLIENT_ID = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2})+$", re.I)


def parse_system_cfg(text: str) -> dict[str, str]:
    cfg = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not _SECRET_KEY.search(key):
            cfg[key] = value
    return cfg


def parse_mca_status(text: str) -> dict[str, str]:
    # La primera linea viene separada por comas, el resto una clave por linea.
    # Se corta en la coma solo si sigue "clave=", asi un deviceName con coma no se rompe.
    status = {}
    for line in text.splitlines():
        for pair in _MCA_SPLIT.split(line):
            key, sep, value = pair.strip().partition("=")
            if sep and key:
                status[key] = value
    return status


def classify_role(mca: dict[str, str], cfg: dict[str, str] | None = None) -> Role:
    opmode = mca.get("wlanOpmode", "")
    if opmode.startswith("ap"):
        return "ap"
    if opmode.startswith("sta"):
        return "cpe"
    radio_mode = (cfg or {}).get("radio.1.mode", "")
    if radio_mode == "master":
        return "ap"
    if radio_mode == "managed":
        return "cpe"
    return "unknown"


@dataclass(frozen=True)
class Lease:
    lease_time: int
    mac: str
    ip: str
    hostname: str | None
    client_id: str | None


def parse_dhcpd_leases(text: str) -> list[Lease]:
    leases = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3 or not fields[0].isdigit():
            continue
        extra = fields[3:]
        # Si el router no manda hostname, el 4to campo es el client-id.
        client_id = extra.pop() if extra and _CLIENT_ID.match(extra[-1]) else None
        hostname = " ".join(extra) or None
        leases.append(Lease(int(fields[0]), fields[1].lower(), fields[2], hostname, client_id))
    return leases


@dataclass(frozen=True)
class Station:
    mac: str
    ip: str | None
    name: str | None
    platform: str | None
    firmware: str | None
    mode: str | None
    signal: int | None
    remote_signal: int | None
    noisefloor: int | None
    distance_m: int | None
    dl_linkscore: int | None
    ul_linkscore: int | None
    uptime_s: int | None


def parse_wstalist(text: str) -> list[Station]:
    # La salida puede venir pegada al prompt; tomamos desde el primer '['.
    start = text.find("[")
    if start == -1:
        return []
    raw, _ = json.JSONDecoder().raw_decode(text[start:])
    stations = []
    for s in raw:
        r = s.get("remote") or {}
        stations.append(
            Station(
                mac=s["mac"].lower(),
                ip=s.get("lastip"),
                name=r.get("hostname"),
                platform=r.get("platform"),
                firmware=r.get("version"),
                mode=r.get("mode"),
                signal=s.get("signal"),
                remote_signal=r.get("signal"),
                noisefloor=s.get("noisefloor"),
                distance_m=s.get("distance"),
                dl_linkscore=s.get("dl_linkscore"),
                ul_linkscore=s.get("ul_linkscore"),
                uptime_s=s.get("uptime"),
            )
        )
    return stations
