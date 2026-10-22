"""Test setup: force Demo Mode and use a throwaway SQLite file. Must run before the app is imported."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix='civicclosure_tests_')
os.environ['FORCE_DEMO_MODE'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_tmp, 'test.db')
os.environ['RATE_LIMIT_PER_MINUTE'] = '100000'
os.environ['NEBIUS_API_KEY'] = ''
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app


@pytest.fixture(scope='session', autouse=True)
def _init():
    init_db()


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def ws():
    return 'test-' + uuid.uuid4().hex[:10]


@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c:
        yield c


def headers(ws, role='reporter', reporter='r1'):
    return {'X-Workspace': ws, 'X-Role': role, 'X-Reporter': reporter}


def post_report(client, ws, text, building='Hostel B', detail='', photo=None, reporter='r1'):
    files = {'photo': ('p.jpg', photo, 'image/jpeg')} if photo else None
    r = client.post('/api/reports', headers=headers(ws, 'reporter', reporter), data={'text': text, 'building': building, 'detail': detail}, files=files)
    return r
