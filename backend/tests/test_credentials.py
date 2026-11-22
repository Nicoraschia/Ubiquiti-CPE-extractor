import paramiko
import pytest

from cpe_scanner import collector

CREDS = [("ubnt", "vieja"), ("ubnt", "nueva"), ("admin", "otra")]


SERVER_KEY = ("ssh-rsa", "AAAAB3NzaC1yc2EAAAADAQABAAAAgQDservidor")


class FakeKey:
    def __init__(self, name, b64):
        self.name, self.b64 = name, b64

    def get_name(self):
        return self.name

    def get_base64(self):
        return self.b64


class FakeSSH:
    """Acepta solo la clave `valid`; registra cada intento en `attempts`.

    Imita a paramiko: si hay una host key registrada para el host y no coincide con la del
    servidor, corta en el intercambio de claves, antes de mandar la contrasena.
    """

    valid = "nueva"
    attempts: list[str] = []
    fail_with: type[Exception] | None = None
    server_key = SERVER_KEY

    def __init__(self):
        self.known = {}
        self.policy = None

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def get_host_keys(self):
        test = self

        class Keys:
            def add(self, host, keytype, key):
                test.known[host] = (keytype, key.get_base64())

        return Keys()

    def get_transport(self):
        test = self

        class Transport:
            def get_remote_server_key(self):
                return FakeKey(*test.server_key)

        return Transport()

    def connect(self, host, username, password, **_):
        if host in self.known and self.known[host] != FakeSSH.server_key:
            raise paramiko.BadHostKeyException(host, FakeKey(*FakeSSH.server_key), FakeKey(*self.known[host]))
        if host not in self.known and self.policy is not None:
            self.policy.missing_host_key(self, host, FakeKey(*FakeSSH.server_key))
        FakeSSH.attempts.append(password)
        if FakeSSH.fail_with:
            raise FakeSSH.fail_with("boom")
        if password != FakeSSH.valid:
            raise paramiko.AuthenticationException("Authentication failed.")

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_ssh(monkeypatch):
    FakeSSH.attempts, FakeSSH.valid, FakeSSH.fail_with, FakeSSH.server_key = [], "nueva", None, SERVER_KEY
    monkeypatch.setattr(collector.paramiko, "SSHClient", FakeSSH)
    # La clave registrada se reconstruye desde base64: en el test basta con conservar el texto.
    monkeypatch.setattr(collector, "_pkey", lambda keytype, b64: FakeKey(keytype, b64))


def test_tries_in_order_until_one_works():
    _, slot = collector._connect("h", CREDS, None, 1)
    assert slot == 2
    assert FakeSSH.attempts == ["vieja", "nueva"]


def test_preferred_slot_goes_first():
    _, slot = collector._connect("h", CREDS, 2, 1)
    assert slot == 2
    assert FakeSSH.attempts == ["nueva"]


def test_stale_preferred_slot_falls_back_to_the_rest():
    FakeSSH.valid = "otra"
    _, slot = collector._connect("h", CREDS, 2, 1)
    assert slot == 3
    assert FakeSSH.attempts == ["nueva", "vieja", "otra"]


def test_all_fail_reports_auth_error():
    FakeSSH.valid = "ninguna"
    with pytest.raises(paramiko.AuthenticationException, match="3 probadas"):
        collector._connect("h", CREDS, None, 1)


def test_network_error_does_not_try_other_credentials():
    FakeSSH.fail_with = TimeoutError
    with pytest.raises(TimeoutError):
        collector._connect("h", CREDS, None, 1)
    assert FakeSSH.attempts == ["vieja"]


def test_collect_reports_auth_failure_as_data():
    FakeSSH.valid = "ninguna"
    r = collector.collect("10.0.0.1", CREDS)
    assert r["ok"] is False and "AuthenticationException" in r["error"]


def test_first_contact_returns_host_key_to_pin():
    ssh, slot = collector._connect("h", CREDS, None, 1)
    assert slot == 2 and collector._server_key(ssh) == SERVER_KEY


def test_known_matching_key_logs_in():
    _, slot = collector._connect("h", CREDS, 2, 1, known=SERVER_KEY)
    assert slot == 2 and FakeSSH.attempts == ["nueva"]


def test_changed_host_key_sends_no_password():
    """Suplantacion de un equipo conocido: no se manda ninguna credencial."""
    r = collector.collect("10.0.0.1", CREDS, known=("ssh-rsa", "AAAAotraclave"))
    assert r["ok"] is False
    assert "no se enviaron credenciales" in r["error"]
    assert FakeSSH.attempts == []
