"""Resultados de collector de ejemplo para tests de base de datos."""

AP_MAC = "24:5a:4c:0c:85:33"
CPE_MAC = "b4:fb:e4:6c:a5:df"


def station(**over):
    s = dict(mac=CPE_MAC, ip="192.168.15.115", name="Cliente 1", platform="NanoStation 5AC",
             firmware="WA.v8.7.12", mode="sta-ptmp", signal=-47, remote_signal=-48, noisefloor=-90,
             distance_m=450, dl_linkscore=94, ul_linkscore=92, uptime_s=500090)
    return {**s, **over}


def ap(stations):
    return dict(host="192.168.15.205", ok=True, cred_slot=1, role="ap", mac=AP_MAC, device_id=AP_MAC, name="AP_TEST",
                platform="Rocket 5AC Lite", firmware="XC.v8.7.12", ap_mac=None, signal=-56, ssid="AP-TEST",
                netmode="bridge", shaper_in=None, shaper_out=None, config={}, stations=stations)


def cpe(**over):
    c = dict(host="192.168.15.115", ok=True, cred_slot=2, role="cpe", mac=CPE_MAC, device_id="70:a7:41:1c:84:4a",
             name="CLIENTE_1_SSH", platform="NanoStation 5AC", firmware="WA.v8.7.12", ap_mac=AP_MAC,
             signal=-48, ssid="AP-TEST", netmode="router", shaper_in=10000, shaper_out=5000,
             config={"netmode": "router"},
             leases=[dict(lease_time=1, mac="48:b2:5d:b2:0f:0c", ip="192.168.9.101", hostname="HG8145V5",
                          client_id="01:48:b2:5d:b2:0f:0c")])
    return {**c, **over}
