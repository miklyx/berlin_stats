import os
from pathlib import Path

import psycopg
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres@localhost:5432/postgres")
os.environ["SECRET_PASSWORD"] = "secret"
os.environ["POLL_ON_STARTUP"] = "false"

import db  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def clean_db():
    try:
        db.init_db()
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not available (set DATABASE_URL)")
    with db.get_pool().connection() as conn:
        conn.execute("TRUNCATE polizei, meeting RESTART IDENTITY")
    yield
