import os
import secrets
from dotenv import load_dotenv

load_dotenv()
os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)

from app.testing import validate_test_database

test_url = os.getenv("TEST_DATABASE_URL")
if test_url:
    validate_test_database(test_url, os.getenv("DATABASE_URL"))
# Unit tests never connect to this placeholder engine.
os.environ["DATABASE_URL"] = test_url or "postgresql+psycopg://localhost/smartrecipe_test"

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def engine():
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")  # tests run against the real migration
    eng = create_engine(os.environ["DATABASE_URL"])
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    conn = engine.connect()
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
    trans.rollback()  # every test starts with a clean database
    conn.close()
