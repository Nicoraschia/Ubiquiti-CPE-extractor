"""API contra Postgres real, en un esquema aislado."""

import factories as f
import pytest
from fastapi.testclient import TestClient

from cpe_scanner import db
from cpe_scanner.api import app

pytestmark = pytest.mark.db

AUTH = {"Authorization": "Bearer test-token"}
OTHER_CPE = "aa:bb:cc:00:00:01"


@pytest.fixture
def client(api_env):
    """Inventario: 1 AP con 2 CPE; uno escaneado por SSH (con lease), otro solo visto desde el AP."""
    conn = api_env
    sid = db.add_subnet(conn, "192.168.15.0/24", "Gestion")
    scan = db.start_scan(conn, sid)
    db.save_result(conn, scan, f.ap([
        f.station(),
        f.station(mac=OTHER_CPE, ip="192.168.15.131", name="Cliente Lejano", platform="LiteBeam 5AC Gen2",
                  remote_signal=-74),
    ]))
    db.save_result(conn, scan, f.cpe())
    db.finish_scan(conn, scan, 3, 2, 0)
    return TestClient(app)


def test_requires_token(client):
    assert client.get("/api/devices").status_code == 401
    assert client.get("/api/devices", headers={"Authorization": "Bearer otro"}).status_code == 401
    assert client.get("/health").status_code == 200


def test_docs_expose_bearer_scheme_for_authorize_button(client):
    spec = client.get("/openapi.json").json()
    assert spec["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http", "scheme": "bearer", "description": "Token de sesion (login) o API_TOKEN del .env"
    }
    # El token no aparece como parametro suelto (Swagger no lo mandaria).
    params = spec["paths"]["/api/aps"]["get"].get("parameters", [])
    assert all(p["name"].lower() != "authorization" for p in params)


def test_list_devices_and_filters(client):
    def macs(**params):
        r = client.get("/api/devices", params=params, headers=AUTH)
        assert r.status_code == 200, r.text
        return sorted(d["mac"] for d in r.json()["items"])

    assert len(macs()) == 3
    assert macs(role="cpe") == sorted([f.CPE_MAC, OTHER_CPE])
    assert macs(q="lejano") == [OTHER_CPE]
    assert macs(platform="litebeam") == [OTHER_CPE]
    assert macs(signal_max=-70) == [OTHER_CPE]
    assert macs(source="wstalist") == [OTHER_CPE]
    assert macs(ap=f.AP_MAC) == sorted([f.CPE_MAC, OTHER_CPE])
    assert macs(lan="hg8145") == [f.CPE_MAC]  # buscar por modelo de router del cliente
    assert macs(q="AP_TEST", role="cpe") == sorted([f.CPE_MAC, OTHER_CPE])  # por nombre del AP
    assert macs(q="AP_TEST", role="ap") == [f.AP_MAC]  # su ssid es AP-TEST: '_' no es comodin


def test_list_devices_shape_and_pagination(client):
    r = client.get("/api/devices", params={"role": "cpe", "sort": "signal", "limit": 1}, headers=AUTH).json()
    assert r["total"] == 2 and len(r["items"]) == 1
    item = r["items"][0]
    assert item["mac"] == OTHER_CPE  # -74 es el menor
    assert item["ap_name"] == "AP_TEST"
    page2 = client.get("/api/devices", params={"role": "cpe", "sort": "signal", "limit": 1, "offset": 1},
                       headers=AUTH).json()
    assert page2["total"] == 2 and page2["items"][0]["lan_hosts"] == ["HG8145V5"]


def test_invalid_filters_are_400s_not_500s(client):
    assert client.get("/api/devices", params={"ap": "no-es-mac"}, headers=AUTH).status_code == 422
    assert client.get("/api/devices", params={"sort": "drop table"}, headers=AUTH).status_code == 422


def test_device_detail(client):
    cpe = client.get(f"/api/devices/{f.CPE_MAC}", headers=AUTH).json()
    assert cpe["ap_name"] == "AP_TEST"
    assert [l["hostname"] for l in cpe["leases"]] == ["HG8145V5"]
    assert len(cpe["link_history"]) == 1 and cpe["stations"] == []

    ap = client.get(f"/api/devices/{f.AP_MAC}", headers=AUTH).json()
    assert [s["mac"] for s in ap["stations"]] == [OTHER_CPE, f.CPE_MAC]  # peor senal primero

    assert client.get("/api/devices/00:00:00:00:00:00", headers=AUTH).status_code == 404


def test_aps_summary(client):
    (ap,) = client.get("/api/aps", headers=AUTH).json()
    assert (ap["name"], ap["stations"], ap["worst_signal"]) == ("AP_TEST", 2, -74)


def test_leases_search(client):
    rows = client.get("/api/leases", params={"q": "hg81"}, headers=AUTH).json()
    assert [(r["hostname"], r["cpe_name"], r["ap_name"]) for r in rows] == [("HG8145V5", "CLIENTE_1_SSH", "AP_TEST")]


def test_multi_word_search_requires_all_terms(client, api_env):
    from cpe_scanner import oui

    oui.replace_vendors(api_env, [("48B25D", "HUAWEI TECHNOLOGIES CO.,LTD")])

    def leases(q):
        return [r["hostname"] for r in client.get("/api/leases", params={"q": q}, headers=AUTH).json()]

    assert leases("HUAWEI TECHNOLOGIES 192.168.9.") == ["HG8145V5"]  # fabricante + IP LAN
    assert leases("huawei 192.168.15.115") == ["HG8145V5"]  # fabricante + IP del CPE
    assert leases("huawei AP_TEST") == ["HG8145V5"]  # fabricante + AP
    assert leases("huawei 192.168.18.") == []  # una palabra no esta: no matchea
    assert leases("   ") == ["HG8145V5"]  # vacio = sin filtro

    def devices(**params):
        r = client.get("/api/devices", params=params, headers=AUTH).json()
        return sorted(d["mac"] for d in r["items"])

    assert devices(q="litebeam lejano") == [OTHER_CPE]
    assert devices(q="litebeam CLIENTE_1") == []
    assert devices(lan="huawei 192.168.9.101") == [f.CPE_MAC]
    assert devices(lan="huawei 192.168.9.7") == []


def test_devices_sort_like_a_person_would(client, api_env):
    scan = db.start_scan(api_env, None)
    names = ["AVILA", "abel", "Nuñez", "Ñandu", "AP_10", "AP_2"]
    db.save_result(api_env, scan, f.ap([
        f.station(mac=f"aa:bb:cc:00:01:{i:02x}", ip=f"10.9.0.{i + 1}", name=n, platform="OrdenTest")
        for i, n in enumerate(names)
    ]))

    def order(**params):
        r = client.get("/api/devices", params={"platform": "OrdenTest", **params}, headers=AUTH)
        assert r.status_code == 200, r.text
        return [d["name"] for d in r.json()["items"]]

    expected = ["abel", "AP_2", "AP_10", "AVILA", "Nuñez", "Ñandu"]
    assert order(sort="name") == expected
    assert order(sort="name", order="desc") == expected[::-1]


def test_devices_sort_by_role_and_lan(client):
    def macs(**params):
        return [d["mac"] for d in client.get("/api/devices", params=params, headers=AUTH).json()["items"]]

    assert macs(sort="role")[0] == f.AP_MAC
    assert macs(sort="role", order="desc")[-1] == f.AP_MAC
    # El unico con router LAN va primero en los dos sentidos: los vacios quedan al final.
    assert macs(sort="lan")[0] == macs(sort="lan", order="desc")[0] == f.CPE_MAC


def test_leases_sort(client, api_env):
    from cpe_scanner import oui

    # Se muestran por marca: Mercusys es TP-Link y tiene que quedar junto a ella, no en la M.
    oui.replace_vendors(api_env, [("48B25D", "HUAWEI TECHNOLOGIES CO.,LTD"), ("AC15A2", "TP-Link Systems Inc."),
                                  ("3C5282", "Mercusys Technologies"), ("B827EB", "Raspberry Pi Foundation")])
    scan = db.start_scan(api_env, None)
    db.save_result(api_env, scan, f.cpe(leases=[
        dict(lease_time=1, mac=m, ip=ip, hostname=h, client_id=None) for m, ip, h in [
            ("48:b2:5d:00:00:01", "192.168.9.10", "R10"), ("ac:15:a2:00:00:01", "192.168.9.2", "r2"),
            ("3c:52:82:00:00:01", "192.168.9.30", None), ("b8:27:eb:00:00:01", "10.0.0.5", "Alfa"),
        ]
    ]))

    def ips(**params):
        r = client.get("/api/leases", params=params, headers=AUTH)
        assert r.status_code == 200, r.text
        return [x["ip"] for x in r.json()]

    assert ips(sort="ip") == ["10.0.0.5", "192.168.9.2", "192.168.9.10", "192.168.9.30"]
    assert ips(sort="ip", order="desc") == ["192.168.9.30", "192.168.9.10", "192.168.9.2", "10.0.0.5"]
    assert ips(sort="hostname") == ["10.0.0.5", "192.168.9.2", "192.168.9.10", "192.168.9.30"]  # sin hostname al final
    assert ips(sort="hostname", order="desc")[-1] == "192.168.9.30"
    vendors = ips(sort="vendor")
    assert vendors[0] == "192.168.9.10" and vendors[1] == "10.0.0.5"  # Huawei, Raspberry
    assert set(vendors[2:]) == {"192.168.9.2", "192.168.9.30"}  # TP-Link y Mercusys juntos
    for field in ("mac", "cpe", "cpe_ip", "ap"):
        assert len(ips(sort=field)) == 4
    assert client.get("/api/leases", params={"sort": "drop table"}, headers=AUTH).status_code == 422


def test_leases_pagination(client, api_env):
    scan = db.start_scan(api_env, None)
    leases = [dict(lease_time=i, mac=f"48:b2:5d:00:00:{i:02x}", ip=f"192.168.9.{i}", hostname=f"R{i:02d}",
                   client_id=None) for i in range(1, 6)]
    db.save_result(api_env, scan, f.cpe(leases=leases))

    def page(**params):
        return [r["hostname"] for r in client.get("/api/leases", params=params, headers=AUTH).json()]

    assert page(limit=2) == ["R01", "R02"]
    assert page(limit=2, offset=2) == ["R03", "R04"]
    assert page(limit=2, offset=4) == ["R05"]


def test_vendor_search_keeps_hostname(client, api_env):
    from cpe_scanner import oui

    oui.replace_vendors(api_env, [("48B25D", "HUAWEI TECHNOLOGIES CO.,LTD")])

    rows = client.get("/api/leases", params={"q": "huawei"}, headers=AUTH).json()
    assert [(r["hostname"], r["vendor"]) for r in rows] == [("HG8145V5", "HUAWEI TECHNOLOGIES CO.,LTD")]

    devices = client.get("/api/devices", params={"lan": "huawei"}, headers=AUTH).json()["items"]
    assert [(d["mac"], d["lan_hosts"], d["lan_vendors"]) for d in devices] == [
        (f.CPE_MAC, ["HG8145V5"], ["HUAWEI TECHNOLOGIES CO.,LTD"])
    ]
    assert client.get("/api/leases/vendors", headers=AUTH).json() == [
        {"vendor": "HUAWEI TECHNOLOGIES CO.,LTD", "leases": 1, "hostname_hash": 0}
    ]
    detail = client.get(f"/api/devices/{f.CPE_MAC}", headers=AUTH).json()
    assert detail["leases"][0]["vendor"] == "HUAWEI TECHNOLOGIES CO.,LTD"


def test_subnets_crud(client):
    r = client.post("/api/subnets", json={"cidr": "10.1.2.3/24", "name": "Nueva"}, headers=AUTH)
    assert r.status_code == 201 and r.json()["cidr"] == "10.1.2.0/24"
    assert client.post("/api/subnets", json={"cidr": "no"}, headers=AUTH).status_code == 422
    sid = r.json()["id"]
    r = client.patch(f"/api/subnets/{sid}", json={"enabled": False}, headers=AUTH)
    assert r.json()["enabled"] is False and r.json()["name"] == "Nueva"
    assert client.patch("/api/subnets/9999", json={"enabled": False}, headers=AUTH).status_code == 404


def test_request_scan_queues_once(client):
    r = client.post("/api/scans", json={}, headers=AUTH)
    assert r.status_code == 202
    queued = r.json()["queued"]
    assert len(queued) == 1 and r.json()["already_active"] == []

    again = client.post("/api/scans", json={}, headers=AUTH).json()
    assert again["queued"] == [] and len(again["already_active"]) == 1

    scan = client.get(f"/api/scans/{queued[0]}", headers=AUTH).json()
    assert (scan["status"], scan["trigger"], scan["errors"]) == ("pending", "manual", [])
    assert client.post("/api/scans", json={"subnet_id": 9999}, headers=AUTH).status_code == 404
    assert [s["status"] for s in client.get("/api/scans", headers=AUTH).json()] == ["pending", "done"]
