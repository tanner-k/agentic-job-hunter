import json
from pathlib import Path

from crewai.tools import tool
from playwright.sync_api import sync_playwright

from worker.config import settings
from worker.logging_config import get_logger

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


@tool("Browser Form Fitter")
def browser_tool(url: str, json_instructions: str, requires_resume: bool) -> str:
    """Navigates to a URL, fills form fields with personal data, uploads resume, and submits the application autonomously."""
    try:
        form_data = json.loads(json_instructions)
    except json.JSONDecodeError:
        return "Error: json_instructions must be a valid JSON dictionary."

    resume_path = settings.resume_path
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=50)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            logger.info("browser_navigating", url=url)
            page.goto(url, wait_until="networkidle")

            # Fill form fields
            for field_name, value in form_data.items():
                logger.debug("filling_field", field=field_name)
                try:
                    locator = page.get_by_text(field_name, exact=False).locator(
                        "xpath=following::input[1]"
                    )
                    locator.fill(str(value))
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
                screenshot_path = _SCREENSHOTS_DIR / f"no_submit_{hash(url) & 0xFFFF}.png"
                page.screenshot(path=str(screenshot_path))
                logger.warning("submit_button_not_found", url=url, screenshot=str(screenshot_path))
                _record_application(url, requires_resume, status="failed", error=f"No submit button found. Screenshot: {screenshot_path}")
                return f"Could not find Submit button at {url}. Screenshot: {screenshot_path}"

        except Exception as exc:
            screenshot_path = _SCREENSHOTS_DIR / f"error_{hash(url) & 0xFFFF}.png"
            try:
                page.screenshot(path=str(screenshot_path))
            except Exception:
                pass
            logger.error("browser_error", url=url, error=str(exc))
            _record_application(url, requires_resume, status="failed", error=str(exc))
            return f"Browser error at {url}: {exc}"
        finally:
            browser.close()


def _record_application(url: str, requires_resume: bool, status: str, error: str | None = None) -> None:
    """Write the application outcome to Supabase. Best-effort — never raises."""
    try:
        from worker.db.repository import insert_application
        from worker.models.application_result import ApplicationResult

        # Extract a rough company/title from the URL for the DB record
        from urllib.parse import urlparse
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
