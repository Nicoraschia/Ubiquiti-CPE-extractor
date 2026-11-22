"""Login, sesiones, roles y freno de fuerza bruta, contra Postgres real."""

import pytest
from fastapi.testclient import TestClient

from cpe_scanner import auth
from cpe_scanner.api import app

pytestmark = pytest.mark.db

ADMIN_PW = "faro-norte-cobre-7"
VIEWER_PW = "antena-sur-hierro-3"


@pytest.fixture
def client(api_env):
    auth.create_user(api_env, "admin", ADMIN_PW, "admin")
    auth.create_user(api_env, "tecnico", VIEWER_PW, "viewer")
    return TestClient(app)


def login(client, username, password, ip="10.0.0.1"):
    return client.post("/api/auth/login", json={"username": username, "password": password},
                       headers={"X-Client-IP": ip})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def token_for(client, username, password):
    r = login(client, username, password)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_login_and_me(client):
    r = login(client, "ADMIN ", ADMIN_PW)  # usuario sin distinguir mayusculas ni espacios
    assert r.status_code == 200
    assert r.json()["user"] == {"id": 1, "username": "admin", "role": "admin"}
    me = client.get("/api/auth/me", headers=bearer(r.json()["token"]))
    assert me.json()["username"] == "admin"


def test_wrong_password_and_unknown_user_look_the_same(client):
    a = login(client, "admin", "otra-clave-cualquiera")
    b = login(client, "noexiste", "otra-clave-cualquiera")
    assert (a.status_code, a.json()) == (b.status_code, b.json()) == (401, {"detail": "usuario o clave incorrectos"})


def test_secrets_are_not_stored_in_plain_text(client, api_env):
    token = token_for(client, "admin", ADMIN_PW)
    (pw_hash,) = api_env.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()
    assert pw_hash.startswith("$argon2id$") and ADMIN_PW not in pw_hash
    stored = api_env.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert token.encode() not in bytes(stored)


def test_viewer_reads_but_cannot_write(client):
    h = bearer(token_for(client, "tecnico", VIEWER_PW))
    assert client.get("/api/devices", headers=h).status_code == 200
    assert client.get("/api/scans", headers=h).status_code == 200
    assert client.post("/api/scans", json={}, headers=h).status_code == 403
    assert client.post("/api/subnets", json={"cidr": "10.0.0.0/24"}, headers=h).status_code == 403
    assert client.patch("/api/subnets/1", json={"enabled": False}, headers=h).status_code == 403
    assert client.get("/api/users", headers=h).status_code == 403
    assert client.get("/api/audit", headers=h).status_code == 403


def test_throttle_per_user_blocks_even_the_right_password(client):
    for _ in range(auth.FAILS_PER_USER):
        assert login(client, "admin", "mal-mal-mal-mal").status_code == 401
    assert login(client, "admin", ADMIN_PW).status_code == 429
    assert login(client, "tecnico", VIEWER_PW).status_code == 200  # otro usuario no se ve afectado


def test_throttle_per_ip(client):
    for i in range(auth.FAILS_PER_IP):
        login(client, f"usuario{i}", "mal-mal-mal-mal", ip="10.9.9.9")
    assert login(client, "tecnico", VIEWER_PW, ip="10.9.9.9").status_code == 429
    assert login(client, "tecnico", VIEWER_PW, ip="10.0.0.2").status_code == 200


def test_logout_invalidates_token(client):
    h = bearer(token_for(client, "tecnico", VIEWER_PW))
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_idle_and_old_sessions_expire(client, api_env):
    h = bearer(token_for(client, "tecnico", VIEWER_PW))
    api_env.execute("UPDATE sessions SET last_seen_at = now() - interval '61 minutes'")
    api_env.commit()
    assert client.get("/api/auth/me", headers=h).status_code == 401

    h = bearer(token_for(client, "tecnico", VIEWER_PW))
    api_env.execute("UPDATE sessions SET created_at = now() - interval '13 hours'")
    api_env.commit()
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_admin_manages_users_and_changes_apply_immediately(client):
    admin = bearer(token_for(client, "admin", ADMIN_PW))
    r = client.post("/api/users", json={"username": "Nuevo", "password": "una-clave-segura-9", "role": "viewer"},
                    headers=admin)
    assert r.status_code == 201 and r.json()["username"] == "nuevo"
    assert client.post("/api/users", json={"username": "nuevo", "password": "una-clave-segura-9"},
                       headers=admin).status_code == 409
    assert client.post("/api/users", json={"username": "corto", "password": "corta"}, headers=admin).status_code == 422
    assert client.post("/api/users", json={"username": "x", "password": "una-clave-segura-9"},
                       headers=admin).status_code == 422

    viewer = bearer(token_for(client, "tecnico", VIEWER_PW))
    (tecnico,) = [u for u in client.get("/api/users", headers=admin).json() if u["username"] == "tecnico"]
    assert tecnico["sessions"] == 1
    r = client.patch(f"/api/users/{tecnico['id']}", json={"enabled": False}, headers=admin)
    assert r.json()["enabled"] is False and r.json()["sessions"] == 0
    assert client.get("/api/auth/me", headers=viewer).status_code == 401
    assert login(client, "tecnico", VIEWER_PW).status_code == 401


def test_admin_cannot_lock_themselves_out(client):
    admin = bearer(token_for(client, "admin", ADMIN_PW))
    assert client.patch("/api/users/1", json={"role": "viewer"}, headers=admin).status_code == 400
    assert client.patch("/api/users/1", json={"enabled": False}, headers=admin).status_code == 400


def test_password_change_keeps_current_session_and_closes_others(client):
    here = bearer(token_for(client, "tecnico", VIEWER_PW))
    other = bearer(token_for(client, "tecnico", VIEWER_PW))
    bad = client.post("/api/auth/password", json={"current_password": "no-es-la-clave", "new_password": "x" * 12},
                      headers=here)
    assert bad.status_code == 400
    weak = client.post("/api/auth/password", json={"current_password": VIEWER_PW, "new_password": "tecnico-123456"},
                       headers=here)
    assert weak.status_code == 422  # contiene el usuario
    ok = client.post("/api/auth/password", json={"current_password": VIEWER_PW, "new_password": "nueva-clave-larga-2"},
                     headers=here)
    assert ok.status_code == 204
    assert client.get("/api/auth/me", headers=here).status_code == 200
    assert client.get("/api/auth/me", headers=other).status_code == 401
    assert login(client, "tecnico", "nueva-clave-larga-2").status_code == 200


def test_writes_are_audited(client):
    admin = bearer(token_for(client, "admin", ADMIN_PW))
    login(client, "admin", "mal-mal-mal-mal", ip="10.0.0.7")
    client.post("/api/subnets", json={"cidr": "10.5.0.0/24", "name": "Norte"}, headers=admin)
    actions = [(e["actor"], e["action"]) for e in client.get("/api/audit", headers=admin).json()]
    assert actions[:3] == [("admin", "subnet_add"), ("admin", "login_failed"), ("admin", "login")]
