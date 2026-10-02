"""Seeded, network-independent Chromium coverage of the report UI."""

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e
V2 = "dQw4w9WgXcQ"


@pytest.mark.seeded
def test_home(page, base_url):
    page.goto(base_url)
    expect(page.get_by_role("heading", name="Fact-check any YouTube video")).to_be_visible()
    expect(page.locator("#recent .video-card")).to_have_count(2)
    expect(page.locator("#stats")).to_contain_text("11")


def test_invalid_url(page, base_url):
    page.goto(base_url)
    page.get_by_placeholder("Paste a YouTube link").fill("https://example.com/video")
    page.get_by_role("button", name="Check video", exact=True).click()
    expect(page.locator("#input-error")).to_contain_text("valid YouTube")
    expect(page.locator("#url-input")).to_have_attribute("aria-invalid", "true")


@pytest.mark.seeded
def test_home_submit_existing(page, base_url):
    page.goto(base_url)
    page.locator("#url-input").fill(f"https://youtu.be/{V2}")
    expect(page.locator("#url-preview")).to_contain_text("Ready to check")
    page.locator("#url-input").press("Enter")
    expect(page).to_have_url(f"{base_url}/video/{V2}")
    expect(page.locator(".claim-card")).to_have_count(8)


@pytest.mark.seeded
def test_report_filter_sort_evidence(page, base_url):
    page.goto(f"{base_url}/video/{V2}")
    expect(page.locator(".score-ring")).to_be_visible()
    expect(page.locator(".verdict-summary .verdict-bar")).to_be_visible()
    expect(page.locator(".claim-card")).to_have_count(8)
    page.get_by_role("button", name=re.compile(r"^False 1$")).click()
    expect(page.locator(".claim-card")).to_have_count(1)
    expect(page.locator(".claim-card")).to_contain_text("ten percent")
    page.get_by_role("button", name="All 8", exact=True).click()
    page.get_by_role("button", name="Most check-worthy", exact=True).click()
    expect(page.locator(".claim-card").first).to_have_attribute("id", "claim-4")
    expect(page.locator(".claim-card").nth(1)).to_have_attribute("id", "claim-5")
    page.get_by_role("button", name="Most serious first").click()
    expect(page.locator(".claim-card").first).to_have_attribute("id", "claim-5")
    page.locator(".claim-toggle").first.click()
    expect(page.locator("#claim-5 .claim-body")).to_be_visible()
    expect(page.locator("#claim-5 .sources")).to_contain_text("Refutes")
    expect(page.locator("#claim-5 .source-quote").first).to_contain_text("demo evidence passage")
    expect(page.locator("#claim-5 .source-rating")).to_contain_text("Rating: False")
    expect(page.locator("#claim-5 .other-sources")).to_contain_text("Other sources reviewed (1)")


@pytest.mark.seeded
def test_deep_link_feedback(page, base_url):
    page.goto(f"{base_url}/video/{V2}#claim-3")
    card = page.locator("#claim-3")
    expect(card.locator(".claim-toggle")).to_have_attribute("aria-expanded", "true")
    with page.expect_response(lambda r: r.url.endswith(f"/api/videos/{V2}/claims/3/feedback") and r.request.method == "POST") as response:
        card.get_by_role("button", name=re.compile(r"^Yes")).click()
    assert response.value.status == 204
    expect(card.get_by_role("button", name="Yes 1")).to_have_attribute("aria-pressed", "true")
    page.reload()
    expect(card.get_by_role("button", name="Yes 1")).to_have_attribute("aria-pressed", "true")


@pytest.mark.seeded
def test_legacy(page, base_url):
    page.goto(f"{base_url}/video/jNQXAC9IVRw")
    expect(page.locator(".claim-card")).to_have_count(3)
    expect(page.locator("#claim-1 .claim-tags")).to_contain_text("True")
    expect(page.locator("#claim-2 .claim-tags")).to_contain_text("Mixed")
    expect(page.locator("#claim-3 .claim-tags")).to_contain_text("Mostly true")


@pytest.mark.seeded
def test_failed(page, base_url):
    page.goto(f"{base_url}/video/aaaaaaaaaaa")
    expect(page.get_by_role("button", name="Try again")).to_be_visible()
    expect(page.locator(".empty-state")).to_contain_text("Captions could not be retrieved")


@pytest.mark.seeded
def test_unknown(page, base_url):
    page.goto(f"{base_url}/video/bbbbbbbbbbb")
    expect(page.get_by_role("heading", name="This video hasn't been checked yet.")).to_be_visible()
    expect(page.get_by_role("button", name="Check this video")).to_be_visible()


def test_invalid_report(page, base_url):
    page.goto(f"{base_url}/video/invalid")
    expect(page.get_by_role("heading", name="Report not found")).to_be_visible()


@pytest.mark.seeded
def test_browse(page, base_url):
    page.goto(f"{base_url}/videos")
    expect(page.locator(".video-card")).to_have_count(2)
    page.get_by_role("searchbox", name="Search videos").fill("Demo")
    expect(page.locator(".video-card")).to_have_count(1)
    page.locator("#browse-sort").select_option("lowest")
    expect(page).to_have_url(re.compile(r"sort=lowest"))
    expect(page.locator(".video-card")).to_have_count(1)
    page.reload()
    expect(page.locator("#browse-search")).to_have_value("Demo")
    expect(page.locator("#browse-sort")).to_have_value("lowest")


@pytest.mark.seeded
def test_channel(page, base_url):
    page.goto(f"{base_url}/channel/Demo%20Channel")
    expect(page.get_by_role("heading", name="Demo Channel", exact=True)).to_be_visible()
    expect(page.locator(".video-card")).to_have_count(1)
    expect(page.locator(".score-ring")).to_be_visible()


def test_about(page, base_url):
    page.goto(f"{base_url}/about")
    expect(page.get_by_role("heading", name="Verdict scale")).to_be_visible()
    expect(page.locator(".legend-row")).to_have_count(7)


def test_theme(page, base_url):
    page.goto(base_url)
    before = page.locator("html").get_attribute("data-theme")
    page.locator("#theme-toggle").click()
    after = "dark" if before == "light" else "light"
    expect(page.locator("html")).to_have_attribute("data-theme", after)
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", after)


@pytest.mark.seeded
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_mobile_report(page, base_url, theme):
    page.set_viewport_size({"width": 375, "height": 812})
    page.add_init_script(f"try {{ localStorage.setItem('theme', '{theme}'); }} catch (_) {{}}")
    page.goto(f"{base_url}/video/{V2}")
    expect(page.locator(".claim-card")).to_have_count(8)
    page.locator("#claim-1 .claim-toggle").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.seeded
def test_processing_transition(page, base_url):
    detail = page.request.get(f"{base_url}/api/videos/{V2}").json()
    page.route(f"**/api/videos/{V2}", lambda r: r.fulfill(status=404, json={"detail": "Not found"}))
    payload = dict(status="processing", stage="verifying", completed=3, total=8,
                   progress="Checking claim 3 of 8…", video=detail, claims=detail["claims"][:3])
    page.route(f"**/api/check/{V2}", lambda r: r.fulfill(json=payload))
    page.goto(f"{base_url}/video/{V2}")
    expect(page.get_by_role("progressbar")).to_have_attribute("aria-valuenow", "3")
    expect(page.locator(".claim-card")).to_have_count(3)
    expect(page.locator(".vote-button")).to_have_count(0)
    page.unroute(f"**/api/videos/{V2}")
    payload["status"] = "completed"
    expect(page.locator(".claim-card")).to_have_count(8)
    expect(page.locator(".score-ring")).to_be_visible()
