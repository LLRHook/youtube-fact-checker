import json

import pytest
from starlette.requests import Request

from backend import main
from backend.config import settings


@pytest.mark.parametrize(
    "hops,xff,expected",
    [
        (0, "client, edge, proxy", "127.0.0.1"),
        (1, "client, edge, proxy", "proxy"),
        (2, "client, edge, proxy", "edge"),
        (3, "client, edge, proxy", "client"),
        (5, "client, edge", "client"),
        (1, " , , ", "127.0.0.1"),
        (2, " client , , edge , proxy ", "edge"),
        (1, "x" * 100, "x" * 45),
    ],
)
def test_forwarded_ip_hops(monkeypatch, hops, xff, expected):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", hops)
    request = Request(dict(type="http", headers=[(b"x-forwarded-for", xff.encode())], client=("127.0.0.1", 1234)))
    assert main._get_client_ip(request) == expected


async def test_security_headers(client, monkeypatch):
    monkeypatch.setattr(settings, "BASE_URL", "http://testserver")
    response = await client.get("/api/health")
    assert response.json() == {"status": "ok", "version": "2.0.0", "pipeline_version": 2}
    csp = response.headers["Content-Security-Policy"]
    script = next(part.strip() for part in csp.split(";") if part.strip().startswith("script-src"))
    assert script == "script-src 'self'" and "'unsafe-inline'" not in script
    assert "frame-src https://www.youtube-nocookie.com https://www.youtube.com" in csp
    assert "base-uri 'self'" in csp and "form-action 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "Strict-Transport-Security" not in response.headers
    secure = await client.get("https://testserver/api/health")
    assert "Strict-Transport-Security" not in secure.headers
    monkeypatch.setattr(settings, "BASE_URL", "https://public.example")
    secure = await client.get("/api/health")
    assert secure.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_jsonld_escapes_script_injection():
    title = "</script><script>alert(1)</script> & café"
    blocks = [main._video_jsonld({"title": title}, "url", "image", 50), main._channel_jsonld(title, 1, 50, "url")]
    for block in blocks:
        assert block.count("</script>") == 1 and block.count("<script") == 1
        payload = block.split(">", 1)[1].removesuffix("</script>")
        assert not any(char in payload for char in "<>&")
        assert json.loads(payload)["name"] == title


async def test_about_missing_and_present(client, monkeypatch, tmp_path):
    path = tmp_path / "about.html"
    monkeypatch.setattr(main, "_ABOUT_PATH", path)
    monkeypatch.setattr(main, "_ABOUT_TEMPLATE", None)
    assert (await client.get("/about")).status_code == 404
    path.write_text('<html><a href="__CANONICAL_URL__">About</a></html>', encoding="utf-8")
    response = await client.get("/about")
    assert response.status_code == 200 and f"{settings.BASE_URL}/about" in response.text
    path.write_text("Changed", encoding="utf-8")
    assert (await client.get("/about")).text == response.text


async def test_existing_pages_robots_and_sitemap(client, seed_video, monkeypatch):
    monkeypatch.setattr(main, "_sitemap_cache", None)
    for path in ["/", "/videos", f"/video/{seed_video}", "/channel/TestChannel", "/robots.txt"]:
        response = await client.get(path)
        assert response.status_code == 200
    sitemap = await client.get("/sitemap.xml")
    assert sitemap.status_code == 200 and f"{settings.BASE_URL}/about" in sitemap.text
    assert f"/video/{seed_video}" in sitemap.text
