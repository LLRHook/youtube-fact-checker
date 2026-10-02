"""Local seeded server and browser isolation for frontend E2E tests."""

import asyncio
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
YOUTUBE_REQUESTS = re.compile(r"https?://([^/]*\.)?(youtube|youtube-nocookie|ytimg|googlevideo)\.com/.*")


@contextmanager
def local_server(db_path):
    from scripts.seed_demo import seed

    asyncio.run(seed(db_path))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "DATABASE_PATH": str(db_path), "ANTHROPIC_API_KEY": "test", "BRAVE_API_KEY": "test",
           "QUEUE_INTERVAL_MINUTES": "1440", "BASE_URL": base}
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
                                "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Local server exited with code {process.returncode}")
            try:
                with urlopen(f"{base}/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Local server did not become healthy")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    override = os.environ.get("E2E_BASE_URL")
    if override:
        yield override.rstrip("/")
    else:
        with local_server(tmp_path_factory.mktemp("e2e") / "demo.db") as base:
            yield base


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server


def pytest_collection_modifyitems(items):
    if os.environ.get("E2E_BASE_URL"):
        for item in items:
            if item.get_closest_marker("seeded"):
                item.add_marker(pytest.mark.skip(reason="Requires the local seeded database"))


@pytest.fixture(autouse=True)
def browser_guards(context, page):
    context.route(YOUTUBE_REQUESTS, lambda route: route.abort())
    violations = []
    context.expose_binding("__recordCsp", lambda source, directive: violations.append(directive))
    context.add_init_script("window.__csp = []; document.addEventListener('securitypolicyviolation', e => { window.__csp.push(e.violatedDirective); window.__recordCsp(e.violatedDirective); });")
    errors = []

    def console_error(message):
        url = message.location.get("url", "")
        blocked_video_resource = YOUTUBE_REQUESTS.match(url)
        expected_lookup_404 = "/api/" in url and "404 (Not Found)" in message.text
        if message.type == "error" and not blocked_video_resource and not expected_lookup_404:
            errors.append(message.text)

    page.on("console", console_error)
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield
    assert not errors, errors
    assert not violations, violations
    if not page.is_closed():
        assert page.evaluate("window.__csp || []") == []
