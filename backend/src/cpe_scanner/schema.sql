-- Idempotente: se aplica con `cpe-scanner init-db` en cada deploy.

CREATE TABLE IF NOT EXISTS subnets (
    id          serial PRIMARY KEY,
    cidr        cidr UNIQUE NOT NULL,
    name        text,
    enabled     boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scans (
    id            serial PRIMARY KEY,
    subnet_id     int REFERENCES subnets(id) ON DELETE SET NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    hosts_alive   int,
    hosts_ok      int,
    hosts_failed  int
);

-- Clave = MAC de la interfaz wireless (ath0): es la que el AP ve en wstalist
-- y la que el CPE reporta como apMac, asi ambos lados se unen sin duplicar.
CREATE TABLE IF NOT EXISTS devices (
    mac           macaddr PRIMARY KEY,
    device_id     macaddr,
    ip            inet,
    role          text NOT NULL DEFAULT 'unknown',
    name          text,
    platform      text,
    firmware      text,
    ssid          text,
    ap_mac        macaddr,
    signal        int,
    netmode       text,
    shaper_in     int,
    shaper_out    int,
    config        jsonb,
    -- 'ssh' = entramos al equipo; 'wstalist' = solo lo vimos desde su AP
    source        text NOT NULL,
    last_seen     timestamptz NOT NULL DEFAULT now(),
    last_scan_id  int REFERENCES scans(id) ON DELETE SET NULL
);
-- Credencial (1-based, orden de SCAN_USER / SCAN_USER_2 / ...) que funciono la ultima vez.
ALTER TABLE devices ADD COLUMN IF NOT EXISTS cred_slot int;
CREATE INDEX IF NOT EXISTS devices_ap_mac_idx ON devices (ap_mac);
CREATE INDEX IF NOT EXISTS devices_ip_idx ON devices (ip);

-- Historial por escaneo: base para graficos de senal y deteccion de desconexiones.
CREATE TABLE IF NOT EXISTS ap_links (
    scan_id        int NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    ap_mac         macaddr NOT NULL,
    cpe_mac        macaddr NOT NULL,
    cpe_ip         inet,
    signal         int,
    remote_signal  int,
    noisefloor     int,
    distance_m     int,
    dl_linkscore   int,
    ul_linkscore   int,
    uptime_s       bigint,
    seen_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scan_id, cpe_mac)
);
CREATE INDEX IF NOT EXISTS ap_links_cpe_idx ON ap_links (cpe_mac, seen_at DESC);

CREATE TABLE IF NOT EXISTS lan_leases (
    scan_id     int NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    cpe_mac     macaddr NOT NULL,
    mac         macaddr NOT NULL,
    ip          inet,
    hostname    text,
    client_id   text,
    lease_time  bigint,
    seen_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scan_id, cpe_mac, mac)
);
CREATE INDEX IF NOT EXISTS lan_leases_hostname_idx ON lan_leases (lower(hostname));

CREATE TABLE IF NOT EXISTS scan_errors (
    scan_id  int NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    host     inet NOT NULL,
    error    text NOT NULL
);

-- Fase 2: la tabla scans es tambien la cola de trabajos del worker.
-- status: pending -> running -> done | failed. trigger: cli | manual | schedule.
ALTER TABLE scans ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'done';
ALTER TABLE scans ADD COLUMN IF NOT EXISTS trigger text;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS error text;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS requested_at timestamptz NOT NULL DEFAULT now();
-- Un solo escaneo activo por subnet: encolar dos veces la misma no duplica trabajo.
CREATE UNIQUE INDEX IF NOT EXISTS scans_one_active_per_subnet
    ON scans (subnet_id) WHERE status IN ('pending', 'running');

-- Escaneo SSH del que salen los leases vigentes del CPE. No sirve last_scan_id:
-- ese avanza tambien cuando solo lo vimos desde el AP, sin leer sus leases.
ALTER TABLE devices ADD COLUMN IF NOT EXISTS ssh_scan_id int REFERENCES scans(id) ON DELETE SET NULL;
UPDATE devices SET ssh_scan_id = last_scan_id WHERE ssh_scan_id IS NULL AND source = 'ssh';

-- Fabricante por OUI (lista MA-L de IEEE), la carga `cpe-scanner oui update` o el worker.
CREATE TABLE IF NOT EXISTS oui_vendors (
    prefix      char(6) PRIMARY KEY,  -- 'AABBCC'
    vendor      text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- vendor se agrega al final: CREATE OR REPLACE VIEW solo permite sumar columnas al final.
CREATE OR REPLACE VIEW current_leases AS
SELECT l.*,
       -- Bit "localmente administrada": MAC aleatoria (privacidad de celulares), sin fabricante.
       CASE WHEN (('x' || left(l.mac::text, 2))::bit(8)::int & 2) <> 0 THEN 'MAC privada (aleatoria)'
            ELSE o.vendor END AS vendor
FROM lan_leases l
JOIN devices d ON d.mac = l.cpe_mac AND l.scan_id = d.ssh_scan_id
LEFT JOIN oui_vendors o ON o.prefix = upper(replace(left(l.mac::text, 8), ':', ''));

-- ---------- Fase 3: usuarios de la web ----------
CREATE TABLE IF NOT EXISTS users (
    id                  serial PRIMARY KEY,
    username            text NOT NULL UNIQUE CHECK (username ~ '^[a-z0-9._-]{3,32}$'),
    password_hash       text NOT NULL,  -- Argon2id
    role                text NOT NULL CHECK (role IN ('admin', 'viewer')),
    enabled             boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    password_changed_at timestamptz NOT NULL DEFAULT now(),
    last_login_at       timestamptz
);

-- Se guarda el SHA-256 del token, no el token: un dump de la base no sirve para entrar.
CREATE TABLE IF NOT EXISTS sessions (
    token_hash   bytea PRIMARY KEY,
    user_id      int NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    ip           inet,
    user_agent   text
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id);

-- Intentos fallidos recientes, para frenar fuerza bruta por usuario y por IP.
CREATE TABLE IF NOT EXISTS login_failures (
    id       bigserial PRIMARY KEY,
    at       timestamptz NOT NULL DEFAULT now(),
    username text,
    ip       inet
);
CREATE INDEX IF NOT EXISTS login_failures_at ON login_failures (at);

CREATE TABLE IF NOT EXISTS audit_log (
    id      bigserial PRIMARY KEY,
    at      timestamptz NOT NULL DEFAULT now(),
    user_id int REFERENCES users(id) ON DELETE SET NULL,
    actor   text NOT NULL,
    action  text NOT NULL,
    detail  jsonb,
    ip      inet
);
CREATE INDEX IF NOT EXISTS audit_log_at ON audit_log (at DESC);
