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
        "type": "http", "scheme": "bearer", "description": "Token de API_TOKEN en el .env del servidor"
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
