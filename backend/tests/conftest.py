import os
from urllib.parse import quote

import pytest


def pytest_collection_modifyitems(config, items):
    # Los tests marcados `db` necesitan Postgres: corren dentro de docker compose.
    if os.environ.get("DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="requiere DATABASE_URL")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


def _fresh_schema(name: str):
    import psycopg

    from cpe_scanner import db

    # Esquema aislado por test: no toca los datos reales.
    c = psycopg.connect(os.environ["DATABASE_URL"])
    c.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
    c.execute(f"CREATE SCHEMA {name}")
    c.execute(f"SET search_path TO {name}")
    db.init_schema(c)
    return c


def _drop_schema(c, name: str):
    c.rollback()
    c.execute(f"DROP SCHEMA {name} CASCADE")
    c.commit()
    c.close()


@pytest.fixture
def conn():
    c = _fresh_schema("test_cpe")
    yield c
    _drop_schema(c, "test_cpe")


@pytest.fixture
def api_env(monkeypatch):
    """Conexion de seed + entorno para que la API use un esquema aislado."""
    c = _fresh_schema("test_api")
    url = os.environ["DATABASE_URL"]
    sep = "&" if "?" in url else "?"
    monkeypatch.setenv("DATABASE_URL", f"{url}{sep}options={quote('-csearch_path=test_api')}")
    monkeypatch.setenv("API_TOKEN", "test-token")
    yield c
    _drop_schema(c, "test_api")
