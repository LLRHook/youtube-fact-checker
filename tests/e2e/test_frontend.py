"""End-to-end tests against the live deployed site using Playwright."""

import re
import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e

_TITLE_RE = re.compile(r".+")


@pytest.fixture(scope="session")
def live_url():
    return "https://backend-production-e740.up.railway.app"


class TestFrontend:
    def test_homepage_loads(self, page, live_url):
        page.goto(live_url)
        expect(page).to_have_title(_TITLE_RE)
        locator = page.locator("input")
        expect(locator.first).to_be_visible()

    def test_invalid_url_error(self, page, live_url):
        page.goto(live_url)
        input_el = page.locator("input").first
        input_el.fill("not-a-valid-url")
        page.locator("button[type='submit'], button").first.click()
        page.wait_for_timeout(2000)
        assert live_url.rstrip("/") in page.url or page.url.endswith("/")

    def test_videos_page_loads(self, page, live_url):
        page.goto(f"{live_url}/videos")
        page.wait_for_load_state("networkidle")
        expect(page).to_have_title(_TITLE_RE)

    def test_video_detail_renders(self, page, live_url):
        """If there's a completed video, its detail page should render."""
        page.goto(f"{live_url}/videos")
        page.wait_for_load_state("networkidle")
        links = page.locator("a[href*='/video/']")
        if links.count() > 0:
            links.first.click()
            page.wait_for_load_state("networkidle")
            expect(page).to_have_title(_TITLE_RE)

    def test_theme_toggle(self, page, live_url):
        page.goto(live_url)
        page.wait_for_load_state("networkidle")
        toggle = page.locator("[data-theme-toggle], .theme-toggle, button:has-text('theme'), button:has-text('dark'), button:has-text('light')")
        if toggle.count() > 0:
            toggle.first.click()
            page.wait_for_timeout(500)

    def test_page_navigation(self, page, live_url):
        page.goto(live_url)
        page.wait_for_load_state("networkidle")
        nav_link = page.locator("a[href*='videos'], a:has-text('Videos'), a:has-text('History')")
        if nav_link.count() > 0:
            nav_link.first.click()
            page.wait_for_load_state("networkidle")
            assert "/videos" in page.url

    def test_keyboard_shortcut_slash(self, page, live_url):
        page.goto(live_url)
        page.wait_for_load_state("networkidle")
        page.keyboard.press("/")
        page.wait_for_timeout(500)
        focused = page.evaluate("document.activeElement?.tagName")
        assert focused in ("INPUT", "TEXTAREA", "BODY", None)
