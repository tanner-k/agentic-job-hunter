"""Shared Playwright helpers used by field_inspector_tool and browser_tool."""

from urllib.parse import urljoin

from playwright.sync_api import Page

from worker.logging_config import get_logger

logger = get_logger(__name__)

# Ordered from most specific to least specific to minimise false-positive clicks.
_APPLY_SELECTORS = [
    "a:has-text('Apply for this job online')",
    "a:has-text('Apply for this job')",
    "a:has-text('Apply Now')",
    "a:has-text('Apply now')",
    "button:has-text('Apply for this job online')",
    "button:has-text('Apply for this job')",
    "button:has-text('Apply Now')",
]


def click_through_to_form(page: Page) -> None:
    """Navigate from a job listing page to the actual application form.

    Many job board search results and aggregator sites show a description page
    with an "Apply" link/button.  This function detects those buttons and
    navigates through them so that subsequent DOM extraction or form-filling
    operates on the real application form.

    Strategy (in order):
    1. For ``<a>`` elements with an ``href``: navigate directly to avoid new-tab issues.
    2. For buttons / anchors without ``href``: click and wait for page load.
    3. No match: do nothing (page is already an application form).
    """
    for selector in _APPLY_SELECTORS:
        loc = page.locator(selector)
        if loc.count() > 0:
            href = loc.first.get_attribute("href")
            if href:
                target = urljoin(page.url, href)
                logger.info("navigating_to_apply_form", target=target)
                try:
                    page.goto(target, wait_until="networkidle", timeout=30_000)
                except Exception:
                    page.goto(target, wait_until="domcontentloaded", timeout=20_000)
            else:
                logger.info("clicking_apply_button", selector=selector)
                try:
                    loc.first.click()
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    page.wait_for_timeout(3000)
            return  # stop after first match — only one click-through per page
