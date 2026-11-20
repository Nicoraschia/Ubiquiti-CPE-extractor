"""Integracion contra Postgres real. Corre solo si hay DATABASE_URL (dentro de docker compose)."""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requiere DATABASE_URL")

AP_MAC = "24:5a:4c:0c:85:33"
CPE_MAC = "b4:fb:e4:6c:a5:df"


@pytest.fixture
def conn():
    import psycopg

    from cpe_scanner import db

    # Esquema aislado por test: no toca los datos reales.
    with psycopg.connect(os.environ["DATABASE_URL"]) as c:
        c.execute("DROP SCHEMA IF EXISTS test_cpe CASCADE")
        c.execute("CREATE SCHEMA test_cpe")
        c.execute("SET search_path TO test_cpe")
        db.init_schema(c)
        yield c
        c.rollback()
        c.execute("DROP SCHEMA test_cpe CASCADE")
        c.commit()


def _station(**over):
    s = dict(mac=CPE_MAC, ip="192.168.15.115", name="Cliente 1", platform="NanoStation 5AC",
             firmware="WA.v8.7.12", mode="sta-ptmp", signal=-47, remote_signal=-48, noisefloor=-90,
             distance_m=450, dl_linkscore=94, ul_linkscore=92, uptime_s=500090)
    return {**s, **over}


def _ap(stations):
    return dict(host="192.168.15.205", ok=True, cred_slot=1, role="ap", mac=AP_MAC, device_id=AP_MAC, name="AP_TEST",
                platform="Rocket 5AC Lite", firmware="XC.v8.7.12", ap_mac=None, signal=-56, ssid="AP-TEST",
                netmode="bridge", shaper_in=None, shaper_out=None, config={}, stations=stations)


def _cpe(**over):
    c = dict(host="192.168.15.115", ok=True, cred_slot=2, role="cpe", mac=CPE_MAC, device_id="70:a7:41:1c:84:4a",
             name="CLIENTE_1_SSH", platform="NanoStation 5AC", firmware="WA.v8.7.12", ap_mac=AP_MAC,
             signal=-48, ssid="AP-TEST", netmode="router", shaper_in=10000, shaper_out=5000,
             config={"netmode": "router"},
             leases=[dict(lease_time=1, mac="48:b2:5d:b2:0f:0c", ip="192.168.9.101", hostname="HG8145V5",
                          client_id="01:48:b2:5d:b2:0f:0c")])
    return {**c, **over}


def test_ap_and_cpe_merge_into_one_device(conn):
    from cpe_scanner import db

    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, _ap([_station()]))
    db.save_result(conn, scan, _cpe())

    rows = conn.execute("SELECT mac::text, role, name, source, ap_mac::text, shaper_in FROM devices ORDER BY role").fetchall()
    assert rows == [
        (AP_MAC, "ap", "AP_TEST", "ssh", None, None),
        (CPE_MAC, "cpe", "CLIENTE_1_SSH", "ssh", AP_MAC, 10000),
    ]
    assert conn.execute("SELECT count(*) FROM ap_links").fetchone()[0] == 1
    assert conn.execute("SELECT hostname FROM lan_leases").fetchall() == [("HG8145V5",)]


def test_station_update_does_not_clobber_ssh_fields(conn):
    from cpe_scanner import db

    s1 = db.start_scan(conn, None)
    db.save_result(conn, s1, _cpe())
    s2 = db.start_scan(conn, None)
    db.save_result(conn, s2, _ap([_station(remote_signal=-60, name=None)]))

    name, signal, shaper, source = conn.execute(
        "SELECT name, signal, shaper_in, source FROM devices WHERE mac = %s", (CPE_MAC,)
    ).fetchone()
    assert (name, signal, shaper, source) == ("CLIENTE_1_SSH", -60, 10000, "ssh")


def test_failed_host_goes_to_scan_errors(conn):
    from cpe_scanner import db

    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, {"host": "192.168.15.9", "ok": False, "error": "TimeoutError: timed out"})
    assert conn.execute("SELECT host(host), error FROM scan_errors").fetchall() == [
        ("192.168.15.9", "TimeoutError: timed out")
    ]
    assert conn.execute("SELECT count(*) FROM devices").fetchone()[0] == 0


def test_cred_slot_is_remembered_by_ip(conn):
    from cpe_scanner import db

    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, _ap([_station()]))
    db.save_result(conn, scan, _cpe())
    assert db.cred_slots_by_ip(conn) == {"192.168.15.205": 1, "192.168.15.115": 2}


def test_list_devices_search_by_model_and_ap(conn):
    from cpe_scanner import db

    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, _ap([_station()]))
    rows = db.list_devices(conn, "cpe", "nanostation")
    assert [(r[0], r[7]) for r in rows] == [(CPE_MAC, "AP_TEST")]
