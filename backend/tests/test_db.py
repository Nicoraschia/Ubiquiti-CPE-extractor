"""Integracion contra Postgres real. Corre solo si hay DATABASE_URL (dentro de docker compose)."""

import factories as f
import pytest

pytestmark = pytest.mark.db


def test_ap_and_cpe_merge_into_one_device(conn):
    from cpe_scanner import db

    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, f.ap([f.station()]))
    db.save_result(conn, scan, f.cpe())

    rows = conn.execute("SELECT mac::text, role, name, source, ap_mac::text, shaper_in FROM devices ORDER BY role").fetchall()
    assert rows == [
        (f.AP_MAC, "ap", "AP_TEST", "ssh", None, None),
        (f.CPE_MAC, "cpe", "CLIENTE_1_SSH", "ssh", f.AP_MAC, 10000),
    ]
    assert conn.execute("SELECT count(*) FROM ap_links").fetchone()[0] == 1
    assert conn.execute("SELECT hostname FROM lan_leases").fetchall() == [("HG8145V5",)]


def test_station_update_does_not_clobber_ssh_fields(conn):
    from cpe_scanner import db

    s1 = db.start_scan(conn, None)
    db.save_result(conn, s1, f.cpe())
    s2 = db.start_scan(conn, None)
    db.save_result(conn, s2, f.ap([f.station(remote_signal=-60, name=None)]))

    name, signal, shaper, source = conn.execute(
        "SELECT name, signal, shaper_in, source FROM devices WHERE mac = %s", (f.CPE_MAC,)
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
    db.save_result(conn, scan, f.ap([f.station()]))
    db.save_result(conn, scan, f.cpe())
    assert db.cred_slots_by_ip(conn) == {"192.168.15.205": 1, "192.168.15.115": 2}


def test_list_devices_search_by_model_and_ap(conn):
    from cpe_scanner import db

    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, f.ap([f.station()]))
    rows = db.list_devices(conn, "cpe", "nanostation")
    assert [(r[0], r[7]) for r in rows] == [(f.CPE_MAC, "AP_TEST")]
