import json
from concurrent.futures import ThreadPoolExecutor

from crewai.tools import tool
from playwright.sync_api import Page, sync_playwright

from worker.logging_config import get_logger
from worker.tools.browser_utils import click_through_to_form

logger = get_logger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _extract_fields(page: Page) -> list[str]:
    """Extract visible form field labels from a rendered page.

    Tries in priority order: <label> text, input placeholder/aria-label,
    textarea placeholder/aria-label, select aria-label/name.
    Deduplicates and strips trailing * and : characters.
    """
    fields: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        clean = text.strip().rstrip("*:").strip()
        if clean and clean not in seen and len(clean) < 100:
            seen.add(clean)
            fields.append(clean)

    # 1. Explicit <label> elements
    for label in page.locator("label").all():
        try:
            add(label.inner_text())
        except Exception:
            pass

    # 2. Inputs (not hidden/submit/button/file)
    input_selector = (
        "input:not([type=hidden]):not([type=submit])"
        ":not([type=button]):not([type=file])"
    )
    for inp in page.locator(input_selector).all():
        try:
            for attr in ("placeholder", "aria-label", "name"):
                val = inp.get_attribute(attr) or ""
                if val:
                    add(val)
                    break
        except Exception:
            pass

    # 3. Textareas
    for ta in page.locator("textarea").all():
        try:
            for attr in ("placeholder", "aria-label", "name"):
                val = ta.get_attribute(attr) or ""
                if val:
                    add(val)
                    break
        except Exception:
            pass

    # 4. Select dropdowns
    for sel in page.locator("select").all():
        try:
            for attr in ("aria-label", "name"):
                val = sel.get_attribute(attr) or ""
                if val:
                    add(val)
                    break
        except Exception:
            pass

    return fields


def _inspector_work(url: str) -> str:
    """Run all Playwright logic in a thread (no asyncio loop — sync_playwright safe).

    Extracted from field_inspector_tool so it can be submitted to ThreadPoolExecutor,
    which avoids the "Playwright Sync API inside asyncio loop" error raised when
    CrewAI invokes tools from within its asyncio event loop.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=_USER_AGENT,
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)

            # If this is a listing page, click through to the actual application form.
            click_through_to_form(page)

            try:
                fields = _extract_fields(page)
                requires_resume = page.locator("input[type=file]").count() > 0
            finally:
                browser.close()

        result = {"url": url, "form_fields": fields, "requires_resume": requires_resume}
        logger.info("fields_extracted", url=url, field_count=len(fields))
        return json.dumps(result)

    except Exception as exc:
        logger.error("field_inspection_failed", url=url, error=str(exc))
        return json.dumps(
            {
                "url": url,
                "form_fields": [],
                "requires_resume": False,
                "error": str(exc),
            }
        )


@tool("Field Inspector")
def field_inspector_tool(url: str) -> str:
    """Visit a job application URL and extract the names of all visible form fields.

    Returns a JSON string with keys: url, form_fields (list of label strings),
    requires_resume (bool). On any error returns empty form_fields with an error key.

    Runs all Playwright operations in a ThreadPoolExecutor so they are isolated
    from CrewAI's asyncio event loop (sync_playwright cannot run inside a loop).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_inspector_work, url)
        try:
            return future.result(timeout=90)
        except TimeoutError:
            logger.error("inspector_timeout", url=url)
            return json.dumps(
                {
                    "url": url,
                    "form_fields": [],
                    "requires_resume": False,
                    "error": "Field inspection timed out after 90 seconds",
                }
            )
        except Exception as exc:
            logger.error("inspector_executor_error", url=url, error=str(exc))
            return json.dumps(
                {
                    "url": url,
                    "form_fields": [],
                    "requires_resume": False,
                    "error": f"Inspector execution error: {exc}",
                }
            )
