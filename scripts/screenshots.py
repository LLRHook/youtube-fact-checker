"""Regenerate frontend evidence images using an isolated seeded server."""

import sys
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from tests.e2e.conftest import ROOT, YOUTUBE_REQUESTS, local_server  # noqa: E402


def processing_response(payload, route):
    route.fulfill(json=payload)


def capture(base, output):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for theme in ("light", "dark"):
            context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=theme,
                                          reduced_motion="reduce", device_scale_factor=1)
            context.route(YOUTUBE_REQUESTS, lambda route: route.abort())
            page = context.new_page()
            suffix = "" if theme == "light" else "-dark"
            for path, name, ready in [("/", "home", "#recent .video-card"),
                                      ("/videos", "browse", ".video-card"),
                                      ("/about", "about", ".legend-row")]:
                page.goto(base + path)
                page.locator(ready).first.wait_for()
                page.screenshot(path=str(output / f"{name}{suffix}.png"), full_page=True)
            page.goto(base + "/video/dQw4w9WgXcQ")
            expect(page.locator(".claim-card")).to_have_count(8)
            page.locator("#claim-1 .claim-toggle").click()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(output / f"report-desktop{suffix}.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / f"report-mobile{suffix}.png"), full_page=True)
            detail = page.request.get(base + "/api/videos/dQw4w9WgXcQ").json()
            page.set_viewport_size({"width": 1440, "height": 900})
            page.route("**/api/videos/dQw4w9WgXcQ", lambda r: r.fulfill(status=404, json={"detail": "Not found"}))
            payload = dict(task_id="dQw4w9WgXcQ", status="processing", stage="verifying", completed=3, total=8,
                           progress="Checking claim 3 of 8…", video=detail, claims=detail["claims"][:3])
            page.route("**/api/check/dQw4w9WgXcQ", partial(processing_response, payload))
            page.goto(base + "/video/dQw4w9WgXcQ")
            expect(page.get_by_role("progressbar")).to_have_attribute("aria-valuenow", "3")
            expect(page.locator(".claim-card")).to_have_count(3)
            page.screenshot(path=str(output / f"report-processing{suffix}.png"), full_page=True)
            context.close()
        browser.close()


if __name__ == "__main__":
    output = ROOT / "docs" / "images"
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="factchecker-screenshots-") as temporary:
        with local_server(Path(temporary) / "demo.db") as base:
            capture(base, output)
    print(f"Saved screenshots to {output}")
