import contextlib
import json
from concurrent.futures import ThreadPoolExecutor

from crewai.tools import tool
from playwright.sync_api import Locator, Page, sync_playwright

from worker.logging_config import get_logger
from worker.tools.browser_utils import click_through_to_form

logger = get_logger(__name__)


def _get_input_label(page: Page, element: Locator) -> str:
    """Return the best available label text for a form element Locator.

    Checks in priority order: <label for="id">, wrapping <label> ancestor,
    aria-label attribute, name attribute. Returns empty string if none found.
    """
    # 1. <label for="element_id">
    with contextlib.suppress(Exception):
        el_id = element.get_attribute("id")
        if el_id:
            text = page.locator(f'label[for="{el_id}"]').inner_text()
            if text.strip():
                return text.strip()

    # 2. Wrapping <label> ancestor
    with contextlib.suppress(Exception):
        text = element.locator("xpath=ancestor::label[1]").inner_text()
        if text.strip():
            return text.strip()

    # 3. aria-label attribute
    with contextlib.suppress(Exception):
        text = element.get_attribute("aria-label") or ""
        if text.strip():
            return text.strip()

    # 4. name attribute
    with contextlib.suppress(Exception):
        text = element.get_attribute("name") or ""
        if text.strip():
            return text.strip()

    return ""


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
        with contextlib.suppress(Exception):
            add(label.inner_text())

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
    from worker.tools.stealth import get_context_options, get_launch_args, random_delay

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=get_launch_args(),
            )
            context = browser.new_context(**get_context_options())
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)

            # Pause briefly before extracting fields to let JS-rendered forms settle.
            random_delay(page)

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
