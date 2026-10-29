import os
from dotenv import load_dotenv

load_dotenv()
# Point the whole app at the test database BEFORE importing anything from app.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def engine():
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
