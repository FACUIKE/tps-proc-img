"""
Acceptance test configuration. DO NOT MODIFY.

Redirects the storage folder to a temporary directory BEFORE importing the
application, so the tests do not touch the real data.
"""

import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tp2-tests-"))
STORAGE_DIR = _TMP / "storage"
BACKEND_DIR = Path(__file__).resolve().parent.parent
os.environ["TP_STORAGE_DIR"] = str(STORAGE_DIR)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)
