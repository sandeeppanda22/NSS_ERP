"""
Response compression (api/main.py: GZipMiddleware, minimum_size=1024).

The pages are large (admin.html ~860 KB, admin.js ~460 KB) and the HTML is
served `no-store`, so without compression every visit re-downloads them in
full. These tests need no database: /login and /assets/* are static.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_large_html_page_is_gzipped_when_the_client_accepts_it():
    r = client.get("/login", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    assert "<html" in r.text.lower()          # the client library decoded it
    assert r.headers.get("cache-control") == "no-store"       # other headers survive
    assert "x-content-type-options" in {k.lower() for k in r.headers}


def test_large_static_asset_is_gzipped():
    r = client.get("/assets/js/nss-config.js", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    assert "max-age=86400" in r.headers.get("cache-control", "")


def test_no_compression_when_the_client_does_not_ask_for_it():
    r = client.get("/login", headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200
    assert "content-encoding" not in {k.lower() for k in r.headers}
