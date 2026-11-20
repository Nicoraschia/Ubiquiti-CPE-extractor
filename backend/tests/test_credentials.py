import paramiko
import pytest

from cpe_scanner import collector

CREDS = [("ubnt", "vieja"), ("ubnt", "nueva"), ("admin", "otra")]


class FakeSSH:
    """Acepta solo la clave `valid`; registra cada intento en `attempts`."""

    valid = "nueva"
    attempts: list[str] = []
    fail_with: type[Exception] | None = None

    def set_missing_host_key_policy(self, _):
        pass

    def connect(self, host, username, password, **_):
        FakeSSH.attempts.append(password)
        if FakeSSH.fail_with:
            raise FakeSSH.fail_with("boom")
        if password != FakeSSH.valid:
            raise paramiko.AuthenticationException("Authentication failed.")

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_ssh(monkeypatch):
    FakeSSH.attempts, FakeSSH.valid, FakeSSH.fail_with = [], "nueva", None
    monkeypatch.setattr(collector.paramiko, "SSHClient", FakeSSH)


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
