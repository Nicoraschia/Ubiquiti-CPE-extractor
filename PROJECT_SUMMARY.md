# Ubiquiti CPE Extractor

**Estado:** activo (planificacion de v2 web)
**Ultima actualizacion:** 2026-11-20

## Hecho
- Scripts CLI: `Cpe_leases/ssh_lista_leases.py` (system.cfg + dhcpd.leases) y `Stations on the AP/` (wstalist).
- paramiko fijado a `<4` (airOS dropbear solo ofrece ssh-rsa/ssh-dss).
- `ssh_lista_leases.py` no se corta ante timeout/conexion rechazada.
- `.gitignore` para `*.csv` y `venv/`.

## En curso (rama `v2`)
- Fase 0 hecha en `backend/`: parsers (system.cfg, mca-status, wstalist, dhcpd.leases) con 9 tests, collector SSH por rol, CLI `cpe-scanner` (JSON por linea, concurrente). Probado en vivo 2026-11-20 contra un AP (7 stations) y un CPE (leases OK).
- Confirmado: en el CPE `apMac` (mca-status) es la MAC del AP al que esta asociado; difiere del `deviceId` propio.
- Hallazgo: `wstalist` del AP trae nombre, modelo, firmware, IP y senal de cada CPE -> escaneo de AP frecuente, CPE solo para leases/shaper.
- Plan v2: interfaz web con discovery por subnet, filtros por cualquier campo, vista AP -> CPE, monitoreo en vivo por CPE.
- Stack decidido: FastAPI + worker Python (scanner paramiko) + Postgres + Next.js/shadcn. Docker en servidor de la red del ISP. Escala 500-3000 equipos.

## Proximo
- Fase 1: discovery de subnets + Postgres.
- Fase 2: API + scheduler + jobs manuales.
- Fase 3: UI (tabla filtrable, vista por AP, detalle de CPE).
- Fase 4: vivo por CPE + eventos de desconexion.

## Bloqueos / pendientes
- Fase 1: normalizar tipos (`signal` llega como string desde mca-status y como int desde wstalist).
- Fase 1: verificar si el `deviceId` del CPE coincide con la MAC que muestra el `wstalist` del AP; si no, vincular por `lastip`.
- macOS re-marca como `hidden` el `.pth` del venv de `backend/` y Python lo ignora: correr con `PYTHONPATH=src` (pytest ya lo tiene configurado).
- Bug conocido v1: solo guarda el ultimo lease por CPE; columnas `modelo`/`hostname` estan corridas (en realidad son hostname DHCP / client-id).
- `Cpe_leases/hosts.txt` modificado sin commitear (contiene IPs reales).
