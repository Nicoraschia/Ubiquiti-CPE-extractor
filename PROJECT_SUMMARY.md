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
- Fase 1 validada 2026-11-20 en 192.168.15.0/24: 92 hosts, 10 AP + 69 CPE por SSH + 13 CPE solo via wstalist (fallo de auth), 69 leases, 9.7 s. 0 duplicados, 0 CPE con AP desconocido: la clave MAC ath0 une bien AP<->CPE.
- Fase 1 implementada: Postgres + docker-compose, discovery por subnet (TCP 22), persistencia (devices, ap_links, lan_leases, scans, scan_errors), CLI `init-db | subnet add/list | scan | devices | probe`. 16 tests OK (4 de integracion contra Postgres en contenedor).
- Lab: `docker-lab` (root@192.168.64.5), todo dentro de `/root/ubiquiti_extractor`, todo en Docker. Sync con `git ls-files -co --exclude-standard | tar | ssh`. Discovery de 192.168.15.0/24: 92 hosts con SSH en 3 s.
- Clave de equipo = MAC de `ath0` (`/sys/class/net/ath0/address`), para unir wstalist del AP con el escaneo SSH del CPE.
- Hallazgo: `wstalist` del AP trae nombre, modelo, firmware, IP y senal de cada CPE -> escaneo de AP frecuente, CPE solo para leases/shaper.
- Plan v2: interfaz web con discovery por subnet, filtros por cualquier campo, vista AP -> CPE, monitoreo en vivo por CPE.
- Stack decidido: FastAPI + worker Python (scanner paramiko) + Postgres + Next.js/shadcn. Docker en servidor de la red del ISP. Escala 500-3000 equipos.

## Proximo
- Credenciales multiples: SCAN_USER[_N]/SCAN_PASSWORD[_N] en .env, se prueban en orden, `devices.cred_slot` recuerda cual funciono. Validado 2026-11-20 (scan 2): 92/92 ok en 10.6 s (79 clave 1, 13 clave 2), 80 leases, 0 duplicados.
- Fase 2/3: fabricante por OUI de la MAC (21/69 leases tienen hostname-hash en vez de modelo).
- Fase 2: API + scheduler + jobs manuales.
- Fase 3: UI (tabla filtrable, vista por AP, detalle de CPE).
- Fase 4: vivo por CPE + eventos de desconexion.

## Bloqueos / pendientes
- Reloj de docker-lab atrasado (11 nov vs 20 nov): afecta timestamps de last_seen/scans.
- macOS re-marca como `hidden` el `.pth` del venv de `backend/` y Python lo ignora: correr con `PYTHONPATH=src` (pytest ya lo tiene configurado).
- Bug conocido v1: solo guarda el ultimo lease por CPE; columnas `modelo`/`hostname` estan corridas (en realidad son hostname DHCP / client-id).
- `Cpe_leases/hosts.txt` modificado sin commitear (contiene IPs reales).
