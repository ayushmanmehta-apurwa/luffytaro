import io

from PIL import Image

from app import config, main
from conftest import headers


def test_standard_security_headers_are_sent(client):
    h = client.get('/health').headers
    assert h['x-content-type-options'] == 'nosniff' and h['x-frame-options'] == 'DENY'
    assert h['referrer-policy'] == 'no-referrer' and 'camera=(self)' in h['permissions-policy']
    assert 'frame-ancestors' in h['content-security-policy-report-only']      # default mode never blocks anything
    assert 'content-security-policy' not in h


def test_csp_can_be_enforced_or_turned_off(client, monkeypatch):
    monkeypatch.setattr(config, 'CSP_MODE', 'enforce')
    assert "script-src 'self'" in client.get('/health').headers['content-security-policy']
    monkeypatch.setattr(config, 'CSP_MODE', 'off')
    h = client.get('/health').headers
    assert 'content-security-policy' not in h and 'content-security-policy-report-only' not in h


def test_hsts_only_when_the_request_was_https(client):
    assert 'strict-transport-security' not in client.get('/health').headers
    assert 'max-age' in client.get('/health', headers={'X-Forwarded-Proto': 'https'}).headers['strict-transport-security']


def test_api_json_is_not_cached(client, ws):
    assert client.get('/api/config').headers['cache-control'] == 'no-store'
    assert client.get('/api/tickets', headers=headers(ws)).headers['cache-control'] == 'no-store'


def test_docs_can_be_hidden(monkeypatch):
    assert main._docs_kwargs() == {}
    monkeypatch.setattr(config, 'DISABLE_DOCS', True)
    assert main._docs_kwargs() == {'docs_url': None, 'redoc_url': None, 'openapi_url': None}


def test_rate_limit_is_per_visitor_behind_a_proxy_and_cannot_be_spoofed(client, ws, monkeypatch):
    monkeypatch.setattr(config, 'TRUST_PROXY_HOPS', 1)
    monkeypatch.setattr(config, 'RATE_LIMIT_PER_MINUTE', 3)
    main._hits.clear()
    try:
        def hit(xff):
            return client.post('/api/admin/reset_clock', headers={**headers(ws, 'admin'), 'X-Forwarded-For': xff}).status_code
        assert [hit('forged-1, 1.1.1.1') for _ in range(3)] == [200, 200, 200]
        assert hit('forged-2, 1.1.1.1') == 429          # same real visitor, a different forged value does not help
        assert hit('forged-3, 2.2.2.2') == 200          # a different real visitor has their own bucket
    finally:
        main._hits.clear()


def test_without_a_proxy_forwarded_headers_are_ignored(client, ws, monkeypatch):
    monkeypatch.setattr(config, 'TRUST_PROXY_HOPS', 0)
    monkeypatch.setattr(config, 'RATE_LIMIT_PER_MINUTE', 2)
    main._hits.clear()
    try:
        codes = [client.post('/api/admin/reset_clock', headers={**headers(ws, 'admin'), 'X-Forwarded-For': str(i)}).status_code for i in range(3)]
        assert codes == [200, 200, 429]
    finally:
        main._hits.clear()


def test_image_with_too_many_pixels_is_rejected(client, ws, monkeypatch):
    monkeypatch.setattr(config, 'MAX_IMAGE_PIXELS', 10000)
    buf = io.BytesIO()
    Image.new('RGB', (200, 200), 'white').save(buf, 'PNG')
    r = client.post('/api/reports', headers=headers(ws), data={'text': 'Water pipe is leaking badly'}, files={'photo': ('big.png', buf.getvalue(), 'image/png')})
    assert r.status_code == 413 and 'pixels' in r.json()['detail']


# ---- CORS: the Vercel (frontend) + Render (backend) setup ----

def test_cors_allows_only_the_configured_origin(client, monkeypatch):
    # The middleware list is built at import time from CORS_ORIGINS; conftest does not set it, so check defaults + normalisation here.
    assert 'http://localhost:5173' in config.CORS_ORIGINS
    ok = client.get('/api/config', headers={'Origin': 'http://localhost:5173'})
    assert ok.headers['access-control-allow-origin'] == 'http://localhost:5173'
    bad = client.get('/api/config', headers={'Origin': 'https://evil.example'})
    assert 'access-control-allow-origin' not in bad.headers


def test_cors_origins_are_normalised(monkeypatch):
    import importlib
    monkeypatch.setenv('CORS_ORIGINS', ' https://a.vercel.app/ , https://b.vercel.app ')
    monkeypatch.setenv('FORCE_DEMO_MODE', 'true')
    mod = importlib.reload(config)
    try:
        assert mod.CORS_ORIGINS == ['https://a.vercel.app', 'https://b.vercel.app']
    finally:
        monkeypatch.delenv('CORS_ORIGINS')
        importlib.reload(config)


def test_invalid_cors_regex_stops_startup_with_a_clear_message(monkeypatch):
    import importlib
    monkeypatch.setenv('CORS_ORIGIN_REGEX', '([unclosed')
    try:
        with __import__('pytest').raises(SystemExit, match='CORS_ORIGIN_REGEX'):
            importlib.reload(config)
    finally:
        monkeypatch.delenv('CORS_ORIGIN_REGEX')
        importlib.reload(config)
