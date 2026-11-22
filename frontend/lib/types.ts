export type Role = "admin" | "viewer";

export type Me = { id: number | null; username: string; role: Role };

export type Device = {
  mac: string;
  ip: string | null;
  role: "ap" | "cpe" | "unknown";
  name: string | null;
  platform: string | null;
  firmware: string | null;
  ssid: string | null;
  signal: number | null;
  netmode: string | null;
  shaper_in: number | null;
  shaper_out: number | null;
  source: "ssh" | "wstalist";
  last_seen: string;
  ap_mac: string | null;
  ap_name: string | null;
  lan_hosts: string[] | null;
  lan_vendors: string[] | null;
};

export type DevicePage = {
  total: number;
  limit: number;
  offset: number;
  items: Device[];
};

export type Lease = {
  mac: string;
  ip: string;
  hostname: string | null;
  vendor: string | null;
  client_id: string | null;
  lease_time: number | null;
  seen_at: string;
};

export type Station = {
  mac: string;
  ip: string | null;
  name: string | null;
  platform: string | null;
  signal: number | null;
  source: string;
  last_seen: string;
};

export type LinkSample = {
  seen_at: string;
  ap_mac: string;
  signal: number | null;
  remote_signal: number | null;
  noisefloor: number | null;
  dl_linkscore: number | null;
  ul_linkscore: number | null;
  uptime_s: number | null;
  distance_m: number | null;
};

export type DeviceDetail = Omit<Device, "lan_hosts" | "lan_vendors"> & {
  device_id: string | null;
  ap_ip: string | null;
  config: Record<string, string> | null;
  leases: Lease[];
  stations: Station[];
  link_history: LinkSample[];
};

export type ApSummary = {
  mac: string;
  ip: string | null;
  name: string | null;
  platform: string | null;
  firmware: string | null;
  ssid: string | null;
  last_seen: string;
  stations: number;
  worst_signal: number | null;
  avg_signal: number | null;
};

export type LeaseRow = {
  hostname: string | null;
  vendor: string | null;
  mac: string;
  ip: string;
  client_id: string | null;
  cpe_mac: string;
  cpe_name: string | null;
  cpe_ip: string | null;
  ap_name: string | null;
};

export type VendorCount = {
  vendor: string;
  leases: number;
  hostname_hash: number;
};

export type ScanStatus = "pending" | "running" | "done" | "failed";

export type Scan = {
  id: number;
  subnet_id: number | null;
  cidr: string | null;
  subnet_name: string | null;
  status: ScanStatus;
  trigger: string | null;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  hosts_alive: number | null;
  hosts_ok: number | null;
  hosts_failed: number | null;
  error: string | null;
};

export type ScanDetail = Scan & { errors: { host: string; error: string }[] };

export type Subnet = {
  id: number;
  cidr: string;
  name: string | null;
  enabled: boolean;
  created_at: string;
};

export type User = {
  id: number;
  username: string;
  role: Role;
  enabled: boolean;
  created_at: string;
  last_login_at: string | null;
  password_changed_at: string;
  sessions: number;
};

export type AuditEntry = {
  id: number;
  at: string;
  actor: string;
  action: string;
  detail: Record<string, unknown> | null;
  ip: string | null;
};

// Estado devuelto por las Server Actions de formularios.
export type FormState =
  { ok?: boolean; error?: string; message?: string } | undefined;
