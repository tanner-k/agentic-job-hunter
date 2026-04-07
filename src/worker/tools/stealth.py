"""Browser stealth helpers.

Centralises all anti-detection configuration so both browser_tool and
field_inspector_tool use identical fingerprinting behaviour.
"""

import random

from playwright.sync_api import Page

# Rotate through several realistic desktop user-agent strings.
# Using random.choice() per launch avoids a stable fingerprint across
# the 10 application cycles that run within a single worker session.
_USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)


def get_launch_args() -> list[str]:
    """Return Chromium launch args that reduce automation fingerprinting."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]


def get_context_options() -> dict:
    """Return browser context options with a randomised user-agent."""
    return {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": random.choice(_USER_AGENTS),
        "locale": "en-US",
        "timezone_id": "America/Los_Angeles",
        "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
    }


def random_delay(page: Page, min_ms: int = 500, max_ms: int = 2000) -> None:
    """Wait a random duration to simulate human pacing between page actions."""
    page.wait_for_timeout(random.randint(min_ms, max_ms))
