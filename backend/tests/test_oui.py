import factories as f
import pytest

from cpe_scanner import db, oui

CSV = """Registry,Assignment,Organization Name,Organization Address
MA-L,48B25D,"HUAWEI TECHNOLOGIES CO.,LTD","No.2 Xin Cheng Road, Dongguan  CN 523808 "
MA-L,cc2d21,"Tenda Technology Co.,Ltd.Dongguan branch","Dongguan CN"
MA-L,ZZZZZZ,Prefijo invalido,
MA-L,123456,,
"""


def test_parse_oui_csv_normalizes_and_skips_invalid():
    assert oui.parse_oui_csv(CSV) == [
        ("48B25D", "HUAWEI TECHNOLOGIES CO.,LTD"),
        ("CC2D21", "Tenda Technology Co.,Ltd.Dongguan branch"),
    ]


@pytest.mark.db
def test_lease_gets_vendor_and_keeps_hostname(conn):
    oui.replace_vendors(conn, oui.parse_oui_csv(CSV))
    scan = db.start_scan(conn, None)
    lease_priv = dict(lease_time=2, mac="da:a1:19:00:00:01", ip="192.168.9.50", hostname="Pixel-8", client_id=None)
    lease_unknown = dict(lease_time=3, mac="00:00:00:00:00:01", ip="192.168.9.51", hostname=None, client_id=None)
    db.save_result(conn, scan, f.cpe(leases=[*f.cpe()["leases"], lease_priv, lease_unknown]))

    rows = conn.execute("SELECT host(ip), hostname, vendor FROM current_leases ORDER BY ip").fetchall()
    assert rows == [
        ("192.168.9.50", "Pixel-8", "MAC privada (aleatoria)"),
        ("192.168.9.51", None, None),
        ("192.168.9.101", "HG8145V5", "HUAWEI TECHNOLOGIES CO.,LTD"),
    ]


@pytest.mark.db
def test_replace_vendors_is_atomic_and_refuses_empty(conn):
    oui.replace_vendors(conn, [("AABBCC", "Viejo")])
    oui.replace_vendors(conn, [("112233", "Nuevo")])
    assert conn.execute("SELECT prefix, vendor FROM oui_vendors").fetchall() == [("112233", "Nuevo")]
    with pytest.raises(ValueError):
        oui.replace_vendors(conn, [])
    assert conn.execute("SELECT count(*) FROM oui_vendors").fetchone()[0] == 1


@pytest.mark.db
def test_staleness(conn):
    assert oui.is_stale(conn)  # vacia
    oui.replace_vendors(conn, [("112233", "Nuevo")])
    assert not oui.is_stale(conn)
    conn.execute("UPDATE oui_vendors SET updated_at = now() - interval '8 days'")
    conn.commit()
    assert oui.is_stale(conn)


@pytest.mark.db
def test_refresh_failure_keeps_existing_list(conn, monkeypatch):
    oui.replace_vendors(conn, [("112233", "Nuevo")])
    conn.execute("UPDATE oui_vendors SET updated_at = now() - interval '8 days'")
    conn.commit()

    def offline():
        raise OSError("sin red")

    monkeypatch.setattr(oui, "download", offline)
    oui.refresh_if_stale(conn)  # no lanza
    assert conn.execute("SELECT vendor FROM oui_vendors").fetchall() == [("Nuevo",)]
