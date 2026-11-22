# Ubiquiti CPE Extractor

**Estado:** activo (v2 completo en lab: backend + web; Fase 4 pendiente)
**Ultima actualizacion:** 2026-11-22

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
- Lab: `docker-lab` (root@192.168.64.5), todo dentro de `/root/ubiquiti_extractor`, todo en Docker. Deploy: el servidor es un clone de `v2`; `git pull --ff-only` via contenedor `alpine/git:2.54.1` + `docker compose build scanner` + `init-db`. Solo se despliega lo commiteado y pusheado. Discovery de 192.168.15.0/24: 92 hosts con SSH en 3 s.
- Clave de equipo = MAC de `ath0` (`/sys/class/net/ath0/address`), para unir wstalist del AP con el escaneo SSH del CPE.
- Fase 2 hecha y desplegada en lab (2026-11-20): cola de escaneos en tabla `scans` (sin Redis), worker con programado cada SCAN_INTERVAL_MIN (60) + escaneos manuales; API FastAPI con token Bearer en 127.0.0.1:8000: `/api/devices` (filtros q, role, ap, platform, lan, source, signal_max, sort, paginado), `/api/devices/{mac}` (leases, stations, historial), `/api/aps`, `/api/leases`, `/api/subnets`, `/api/scans`. 41 tests OK en lab. Validado: scan programado y manual por API 92/92, dedupe de pedidos, 17 CPE con router HG8245W5.
- Fabricante por OUI hecho (2026-11-20): tabla `oui_vendors` (IEEE MA-L, 40.5k), refresco semanal en el worker, columna `vendor` en `current_leases` junto al hostname, filtros `lan`/`q` buscan por fabricante, `/api/leases/vendors`. Real: 80/80 leases con fabricante; los 19 hostname-hash son todos "Huawei Device Co., Ltd.". 48 tests OK.
- Credenciales multiples: SCAN_USER[_N]/SCAN_PASSWORD[_N] en .env, se prueban en orden, `devices.cred_slot` recuerda cual funciono. Validado 2026-11-20 (scan 2): 92/92 ok en 10.6 s (79 clave 1, 13 clave 2), 80 leases, 0 duplicados.
- Busqueda multi-palabra (2026-11-22): `q` y `lan` separan por espacios y exigen que cada palabra matchee algun campo (ej. `huawei 192.168.18.`). `/api/leases` busca tambien en IP/nombre del CPE y del AP. 49 tests OK, desplegado.
- Tests de Postgres sin commitear: imagen temporal con `tar --format ustar | ssh docker build -` (no escribe en el checkout del servidor).
- Hallazgo: `wstalist` del AP trae nombre, modelo, firmware, IP y senal de cada CPE -> escaneo de AP frecuente, CPE solo para leases/shaper.
- Plan v2: interfaz web con discovery por subnet, filtros por cualquier campo, vista AP -> CPE, monitoreo en vivo por CPE.
- Stack decidido: FastAPI + worker Python (scanner paramiko) + Postgres + Next.js. Docker en servidor de la red del ISP. Escala 500-3000 equipos.
- Fase 3 hecha y desplegada en lab (2026-11-22), https://192.168.64.5:
  - Auth en la API: usuarios locales Argon2id, sesiones opacas (SHA-256 en Postgres, 60 min inactividad / 12 h max), roles admin/viewer aplicados en la API, freno de fuerza bruta (5 por usuario, 20 por IP en 15 min), auditoria. CLI `user add|passwd|list`.
  - Web Next.js 16 BFF (`frontend/`): login, Equipos (filtros GET, orden, paginado), detalle CPE/AP (sparkline de senal, enlace, LAN), APs, Routers LAN, Escaneos (auto-refresco), Subnets, Usuarios, Auditoria, Cuenta, paleta de busqueda `/` o Cmd+K. Sistema de diseno en DESIGN.md (IBM Plex, color solo para estado).
  - Seguridad: cookie `__Host-` httpOnly/Secure/Strict (el navegador nunca ve la API ni el token), CSP estricto con nonce por request (sin cacheComponents), Caddy HTTPS con CA interna y HSTS como unico servicio expuesto, red `edge` aislada (Caddy no alcanza API ni Postgres), contenedores sin root, read-only y sin capabilities.
  - Auditoria /cso: 2 hallazgos corregidos. Open redirect post-login con TAB en `next` y host keys SSH (TOFU en `ssh_host_keys`: si la clave cambia no se mandan credenciales; un admin acepta el equipo reemplazado desde el detalle del escaneo). Verificado en vivo contra equipos reales.
  - Tests: 66 backend contra Postgres, 3 unitarios web, QA Playwright 29/29 (admin, viewer, CSP, cookie, open redirect, movil, claro/oscuro).

## Proximo
- Opcional: normalizar fabricante a marca (Huawei Technologies/Huawei Device -> Huawei; TP-LINK/TP-Link Systems/Mercury/Mercusys -> TP-Link) para filtros mas simples.
- Fase 4: vivo por CPE + eventos de desconexion.
- Crear el primer admin real: `docker compose run --rm scanner user add <usuario> --role admin`.
- Instalar la raiz de la CA de Caddy en las PCs de soporte (o usar un certificado propio).
- Riesgo residual SSH: una IP nunca vista recibe credenciales en su primer contacto (TOFU no lo cubre). Opcion: aprobar hosts nuevos que no aparezcan en el wstalist de un AP.
- Opcional: renombrar subnets desde la web (192.168.18.0/24 quedo con nombre "string").

## Bloqueos / pendientes
- 22 leases detras de CPE 192.168.18.x salen sin AP: sus AP no estan en ninguna subnet cargada.
- 192.168.18.0/24: los escaneos 65 y 68 encontraron 0 equipos (antes 67). Revisar conectividad/ruta desde el servidor.
- paramiko 3.5.1 tiene CVE-2026-44405 (SHA-1 en RSA): riesgo aceptado, airOS dropbear solo habla ssh-rsa.
- Rotar API_TOKEN (quedo expuesto en una captura); ahora es opcional, la web no lo usa.
- macOS re-marca como `hidden` el `.pth` del venv de `backend/` y Python lo ignora: correr con `PYTHONPATH=src` (pytest ya lo tiene configurado).
- Bug conocido v1: solo guarda el ultimo lease por CPE; columnas `modelo`/`hostname` estan corridas (en realidad son hostname DHCP / client-id).
- `Cpe_leases/hosts.txt` modificado sin commitear (contiene IPs reales).
