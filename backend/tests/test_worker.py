"""Cola de escaneos y worker, contra Postgres real."""

import pytest

from cpe_scanner import db, worker

pytestmark = pytest.mark.db


def _status(conn, scan_id):
    return conn.execute("SELECT status, error FROM scans WHERE id = %s", (scan_id,)).fetchone()


def test_enqueue_is_deduplicated_per_subnet(conn):
    sid = db.add_subnet(conn, "192.168.15.0/24", "Gestion")
    first = db.enqueue_scan(conn, sid, "manual")
    assert first is not None
    assert db.enqueue_scan(conn, sid, "schedule") is None
    # El CLI tampoco arranca uno en paralelo sobre la misma subnet.
    assert db.start_scan(conn, sid) is None


def test_subnet_can_be_queued_again_after_finishing(conn):
    sid = db.add_subnet(conn, "192.168.15.0/24", None)
    first = db.enqueue_scan(conn, sid, "manual")
    db.finish_scan(conn, first, 0, 0, 0)
    assert db.enqueue_scan(conn, sid, "manual") is not None


def test_add_subnet_normalizes_host_bits(conn):
    sid = db.add_subnet(conn, "192.168.15.77/24", None)
    assert db.list_subnets(conn) == [(sid, "192.168.15.0/24", None, True)]


def test_schedule_all_only_enabled_subnets(conn):
    on = db.add_subnet(conn, "10.0.0.0/24", "on")
    off = db.add_subnet(conn, "10.0.1.0/24", "off")
    conn.execute("UPDATE subnets SET enabled = false WHERE id = %s", (off,))
    conn.commit()
    queued = worker.schedule_all(conn)
    assert len(queued) == 1
    assert conn.execute("SELECT subnet_id, trigger FROM scans").fetchall() == [(on, "schedule")]
    assert worker.schedule_all(conn) == []  # ya hay uno pendiente


def test_process_one_runs_oldest_pending_and_marks_done(conn, monkeypatch):
    a = db.add_subnet(conn, "10.0.0.0/24", "a")
    b = db.add_subnet(conn, "10.0.1.0/24", "b")
    scan_a = db.enqueue_scan(conn, a, "manual")
    scan_b = db.enqueue_scan(conn, b, "manual")
    seen = []
    monkeypatch.setattr(worker, "run_scan", lambda c, scan_id, cidr, creds, w: seen.append(cidr) or (3, 2, 1))

    assert worker.process_one(conn, [("u", "p")], 1) is True
    assert seen == ["10.0.0.0/24"]
    assert _status(conn, scan_a) == ("done", None)
    assert _status(conn, scan_b) == ("pending", None)
    assert conn.execute("SELECT hosts_alive, hosts_ok, hosts_failed FROM scans WHERE id = %s", (scan_a,)).fetchone() == (3, 2, 1)


def test_process_one_empty_queue(conn):
    assert worker.process_one(conn, [("u", "p")], 1) is False


def test_process_one_without_credentials_fails_the_scan(conn):
    sid = db.add_subnet(conn, "10.0.0.0/24", None)
    scan_id = db.enqueue_scan(conn, sid, "manual")
    assert worker.process_one(conn, None, 1) is True
    status, error = _status(conn, scan_id)
    assert status == "failed" and "SCAN_USER" in error


def test_process_one_survives_scan_crash(conn, monkeypatch):
    sid = db.add_subnet(conn, "10.0.0.0/24", None)
    scan_id = db.enqueue_scan(conn, sid, "manual")

    def boom(*_):
        raise ValueError("salida inesperada")

    monkeypatch.setattr(worker, "run_scan", boom)
    assert worker.process_one(conn, [("u", "p")], 1) is True
    assert _status(conn, scan_id) == ("failed", "ValueError: salida inesperada")


def test_fail_stale_scans_spares_recent_cli_runs(conn):
    a = db.add_subnet(conn, "10.0.0.0/24", None)
    b = db.add_subnet(conn, "10.0.1.0/24", None)
    c = db.add_subnet(conn, "10.0.2.0/24", None)
    from_worker = db.enqueue_scan(conn, a, "manual")
    db.claim_scan(conn)
    cli_recent = db.start_scan(conn, b)
    cli_old = db.start_scan(conn, c)
    conn.execute("UPDATE scans SET started_at = now() - interval '2 hours' WHERE id = %s", (cli_old,))
    conn.commit()

    assert db.fail_stale_scans(conn) == 2
    assert _status(conn, from_worker)[0] == "failed"
    assert _status(conn, cli_recent)[0] == "running"
    assert _status(conn, cli_old)[0] == "failed"
