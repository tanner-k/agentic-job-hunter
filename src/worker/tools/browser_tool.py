import contextlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from crewai.tools import tool
from playwright.sync_api import sync_playwright

from worker.config import settings
from worker.logging_config import get_logger
from worker.tools.browser_utils import click_through_to_form

logger = get_logger(__name__)

_SCREENSHOTS_DIR = Path("./worker/screenshots")

# task_id is set by crew.py before each run so browser_tool can tag Supabase rows
_current_task_id: str | None = None


def set_current_task_id(task_id: str | None) -> None:
    global _current_task_id
    _current_task_id = task_id


def _load_personal_data() -> dict:
    """Load personal data from local JSON file. Never leaves the machine."""
    path = settings.personal_data_path
    if not path.exists():
        logger.warning("personal_data_not_found", path=str(path))
        return {}
    with path.open() as f:
        return json.load(f)


def _browser_work(url: str, json_instructions: str, requires_resume: bool) -> str:
    """Run all Playwright logic in a thread (no asyncio loop — sync_playwright safe).

    Extracted from browser_tool so it can be submitted to ThreadPoolExecutor,
    which avoids the "Playwright Sync API inside asyncio loop" error raised when
    CrewAI invokes tools from within its asyncio event loop.
    """
    try:
        form_data = json.loads(json_instructions)
    except json.JSONDecodeError:
        return "Error: json_instructions must be a valid JSON dictionary."

    resume_path = settings.resume_path
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    from worker.tools.stealth import get_context_options, get_launch_args, random_delay

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=settings.headless,
            args=get_launch_args(),
        )
        context = browser.new_context(**get_context_options())
        page = context.new_page()
        try:
            logger.info("browser_navigating", url=url)
            # networkidle can time out on pages that keep background XHR alive;
            # fall back to domcontentloaded so the page is at least rendered.
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)

            # Pause briefly to mimic human reading time before filling.
            random_delay(page)

            # If this is a listing page, click through to the actual application form.
            click_through_to_form(page)

            # Fill form fields with per-keystroke delays to simulate human typing.
            for field_name, value in form_data.items():
                logger.debug("filling_field", field=field_name)
                try:
                    locator = page.get_by_text(field_name, exact=False).locator(
                        "xpath=following::input[1]"
                    )
                    locator.fill(str(value))
                    random_delay(page, min_ms=200, max_ms=600)
                except Exception:
                    logger.debug("field_not_found", field=field_name)

            # Upload resume
            if requires_resume:
                if resume_path.exists():
                    logger.info("uploading_resume", path=str(resume_path))
                    file_input = page.locator("input[type='file']")
                    if file_input.count() > 0:
                        file_input.first.set_input_files(str(resume_path))
                    else:
                        logger.warning("no_file_input_found", url=url)
                else:
                    logger.error("resume_not_found", path=str(resume_path))

            # Submit
            submit_button = page.locator(
                "button:has-text('Submit Application'), "
                "button:has-text('Submit'), "
                "button:has-text('Apply'), "
                "input[type='submit']"
            )
            if submit_button.count() > 0:
                submit_button.first.click()
                page.wait_for_timeout(3000)
                logger.info("application_submitted", url=url)
                _record_application(url, requires_resume, status="applied")
                return f"Successfully submitted application at {url}"
            else:
                screenshot_path = (
                    _SCREENSHOTS_DIR / f"no_submit_{hash(url) & 0xFFFF}.png"
                )
                page.screenshot(path=str(screenshot_path))
                logger.warning(
                    "submit_button_not_found",
                    url=url,
                    screenshot=str(screenshot_path),
                )
                _record_application(
                    url,
                    requires_resume,
                    status="failed",
                    error=f"No submit button found. Screenshot: {screenshot_path}",
                )
                return f"Could not find Submit button at {url}. Screenshot: {screenshot_path}"

        except Exception as exc:
            screenshot_path = _SCREENSHOTS_DIR / f"error_{hash(url) & 0xFFFF}.png"
            with contextlib.suppress(Exception):
                page.screenshot(path=str(screenshot_path))
            logger.error("browser_error", url=url, error=str(exc))
            _record_application(url, requires_resume, status="failed", error=str(exc))
            return f"Browser error at {url}: {exc}"
        finally:
            browser.close()


@tool("Browser Form Fitter")
def browser_tool(url: str, json_instructions: str, requires_resume: bool) -> str:
    """Navigate to a job application URL, fill form fields, upload resume, and submit.

    Runs all Playwright operations in a ThreadPoolExecutor so they are isolated
    from CrewAI's asyncio event loop (sync_playwright cannot run inside a loop).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_browser_work, url, json_instructions, requires_resume)
        try:
            return future.result(timeout=120)
        except TimeoutError:
            logger.error("browser_timeout", url=url)
            _record_application(
                url,
                requires_resume,
                status="failed",
                error="Browser operation timed out",
            )
            return f"Browser operation timed out at {url}"
        except Exception as exc:
            logger.error("browser_executor_error", url=url, error=str(exc))
            return f"Browser execution error at {url}: {exc}"


def _record_application(
    url: str, requires_resume: bool, status: str, error: str | None = None
) -> None:
    """Write the application outcome to Supabase. Best-effort — never raises."""
    try:
        from urllib.parse import urlparse

        from worker.db.repository import insert_application
        from worker.models.application_result import ApplicationResult

        domain = urlparse(url).netloc.replace("www.", "")

        result = ApplicationResult(
            job_url=url,
            company=domain,
            job_title="Applied via Browser",
            status=status,
            search_task_id=_current_task_id,
            requires_resume=requires_resume,
            error_message=error,
        )
        insert_application(result)
    except Exception as exc:
        logger.error("application_record_failed", url=url, error=str(exc))
