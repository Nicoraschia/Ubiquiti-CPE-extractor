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
