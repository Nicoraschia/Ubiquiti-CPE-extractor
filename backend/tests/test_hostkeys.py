"""Host keys SSH registradas en el primer contacto (TOFU) y su olvido controlado."""

import factories as f
import pytest
from fastapi.testclient import TestClient

from cpe_scanner import auth, db
from cpe_scanner.api import app

pytestmark = pytest.mark.db

KEY = ("ssh-rsa", "AAAAB3NzaC1yc2EAAAADAQABAAAAgQDprimera")


def test_first_contact_pins_key_and_never_overwrites_it(conn):
    scan = db.start_scan(conn, None)
    db.save_result(conn, scan, {**f.cpe(), "host_key": KEY})
    assert db.host_keys(conn) == {"192.168.15.115": KEY}

    # Un resultado con otra clave para la misma IP no reemplaza la registrada.
    db.save_result(conn, scan, {**f.cpe(), "host_key": ("ssh-rsa", "AAAAotra")})
    assert db.host_keys(conn) == {"192.168.15.115": KEY}

    assert db.forget_host_key(conn, "192.168.15.115") is True
    assert db.host_keys(conn) == {}
    assert db.forget_host_key(conn, "192.168.15.115") is False


def test_only_admin_can_forget_a_key_and_it_is_audited(api_env):
    scan = db.start_scan(api_env, None)
    db.save_result(api_env, scan, {**f.cpe(), "host_key": KEY})
    auth.create_user(api_env, "jefe", "faro-norte-cobre-7", "admin")
    auth.create_user(api_env, "tecnico", "antena-sur-hierro-3", "viewer")
    client = TestClient(app)

    def bearer(u, p):
        token = client.post("/api/auth/login", json={"username": u, "password": p}).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    viewer, admin = bearer("tecnico", "antena-sur-hierro-3"), bearer("jefe", "faro-norte-cobre-7")
    assert client.delete("/api/hostkeys/192.168.15.115", headers=viewer).status_code == 403
    assert client.delete("/api/hostkeys/no-es-ip", headers=admin).status_code == 422
    assert client.delete("/api/hostkeys/192.168.15.115", headers=admin).status_code == 204
    assert client.delete("/api/hostkeys/192.168.15.115", headers=admin).status_code == 404
    actions = [e["action"] for e in client.get("/api/audit", headers=admin).json()]
    assert actions[0] == "hostkey_forget"
