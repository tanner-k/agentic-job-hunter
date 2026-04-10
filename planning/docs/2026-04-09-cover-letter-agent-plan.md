# Cover Letter Writer Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Cover Letter Writer agent to the application pipeline that generates tailored, job-specific cover letters (plain text + PDF) when a job application requires one.

**Architecture:** A new `CoverLetterWriter` CrewAI agent is inserted between the Evaluator and Browser in the sequential crew. The Field Inspector is extended to detect cover letter fields and extract job description text from the page DOM. The Browser is updated to fill cover letter text fields and upload cover letter PDFs.

**Tech Stack:** Python 3.12, CrewAI, Playwright (sync API), reportlab (PDF rendering), Pydantic, pytest

---

## File Map

| Action | Path |
|--------|------|
| Modify | `src/worker/models/inspected_job.py` |
| Modify | `src/worker/models/application_packet.py` |
| Modify | `src/worker/tools/field_inspector_tool.py` |
| Modify | `src/worker/config.py` |
| Modify | `src/worker/tools/browser_tool.py` |
| Modify | `src/worker/crew.py` |
| Create | `src/worker/tools/cover_letter_context_loader.py` |
| Create | `src/worker/tools/cover_letter_renderer.py` |
| Create | `src/worker/agents/cover_letter_writer.py` |
| Modify | `src/worker/tests/models/test_crew_models.py` |
| Modify | `src/worker/tests/tools/test_field_inspector_tool.py` |
| Modify | `src/worker/tests/tools/test_browser_tool.py` |
| Modify | `src/worker/tests/test_config.py` |
| Modify | `src/worker/tests/test_crew.py` |
| Create | `src/worker/tests/tools/test_cover_letter_tools.py` |

---

## Task 1: Update Data Models

**Files:**
- Modify: `src/worker/models/inspected_job.py`
- Modify: `src/worker/models/application_packet.py`
- Modify: `src/worker/tests/models/test_crew_models.py`

- [ ] **Step 1: Write failing tests for new model fields**

Add to `src/worker/tests/models/test_crew_models.py`:

```python
def test_inspected_job_has_cover_letter_fields():
    from worker.models.inspected_job import InspectedJob

    job = InspectedJob(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        form_fields=["First Name"],
        requires_resume=False,
        requires_cover_letter=True,
        job_description="We are looking for a talented engineer.",
    )
    assert job.requires_cover_letter is True
    assert job.job_description == "We are looking for a talented engineer."


def test_application_packet_has_cover_letter_fields():
    import json
    from worker.models.application_packet import ApplicationPacket

    packet = ApplicationPacket(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        json_instructions=json.dumps({"Email": "t@example.com"}),
        requires_resume=False,
    )
    assert packet.cover_letter_text is None
    assert packet.cover_letter_path is None


def test_application_packet_cover_letter_fields_accept_values():
    import json
    from worker.models.application_packet import ApplicationPacket

    packet = ApplicationPacket(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        json_instructions=json.dumps({"Email": "t@example.com"}),
        requires_resume=False,
        cover_letter_text="Dear Hiring Manager...",
        cover_letter_path="/tmp/acme_engineer_20260409_120000.pdf",
    )
    assert packet.cover_letter_text == "Dear Hiring Manager..."
    assert packet.cover_letter_path == "/tmp/acme_engineer_20260409_120000.pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/models/test_crew_models.py::test_inspected_job_has_cover_letter_fields \
  src/worker/tests/models/test_crew_models.py::test_application_packet_has_cover_letter_fields \
  src/worker/tests/models/test_crew_models.py::test_application_packet_cover_letter_fields_accept_values \
  -v
```

Expected: FAIL (fields not defined yet)

- [ ] **Step 3: Update `InspectedJob`**

Replace the contents of `src/worker/models/inspected_job.py`:

```python
from pydantic import BaseModel


class InspectedJob(BaseModel):
    """A job listing enriched with form fields extracted from its application page."""

    url: str
    company: str
    job_title: str
    form_fields: list[str]  # exact labels extracted from the rendered DOM
    requires_resume: bool  # True if a non-cover-letter <input type="file"> was found
    requires_cover_letter: bool  # True if a cover-letter-labeled field was found
    job_description: str  # visible page text, trimmed to 4000 chars


class InspectedJobs(BaseModel):
    """All inspected jobs produced by the Field Inspector agent."""

    jobs: list[InspectedJob]
```

- [ ] **Step 4: Update `ApplicationPacket`**

Replace the contents of `src/worker/models/application_packet.py`:

```python
from pydantic import BaseModel


class ApplicationPacket(BaseModel):
    """Instructions for the Browser agent to fill and submit one job application."""

    url: str
    company: str
    job_title: str
    json_instructions: str  # JSON-encoded string: '{"First Name": "Tanner", ...}'
    requires_resume: bool
    cover_letter_text: str | None = None   # plain text for cover letter text fields
    cover_letter_path: str | None = None   # absolute path to rendered PDF


class ApplicationPackets(BaseModel):
    """All application packets produced by the Evaluator agent."""

    job_applications: list[ApplicationPacket]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/models/test_crew_models.py -v
```

Expected: All PASS. The existing `test_inspected_job_fields_and_resume` and `test_application_packet_json_instructions_is_string` will fail because `InspectedJob` now requires `requires_cover_letter` and `job_description`. Fix them:

In `test_crew_models.py`, update the existing tests to include the new required fields:

```python
def test_inspected_job_fields_and_resume():
    from worker.models.inspected_job import InspectedJob

    job = InspectedJob(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        form_fields=["First Name", "Email"],
        requires_resume=True,
        requires_cover_letter=False,
        job_description="",
    )
    assert job.form_fields == ["First Name", "Email"]
    assert job.requires_resume is True


def test_inspected_jobs_holds_list():
    from worker.models.inspected_job import InspectedJob, InspectedJobs

    jobs = InspectedJobs(
        jobs=[
            InspectedJob(
                url="https://a.com",
                company="A",
                job_title="D",
                form_fields=["Email"],
                requires_resume=False,
                requires_cover_letter=False,
                job_description="",
            ),
        ]
    )
    assert len(jobs.jobs) == 1
```

Run again: all model tests should PASS.

- [ ] **Step 6: Commit**

```bash
git add src/worker/models/inspected_job.py src/worker/models/application_packet.py \
  src/worker/tests/models/test_crew_models.py
git commit -m "feat: add cover letter fields to InspectedJob and ApplicationPacket"
```

---

## Task 2: `_get_input_label` Helper (TDD)

**Files:**
- Modify: `src/worker/tools/field_inspector_tool.py`
- Modify: `src/worker/tests/tools/test_field_inspector_tool.py`

- [ ] **Step 1: Write failing tests**

Add to `src/worker/tests/tools/test_field_inspector_tool.py`:

```python
def test_get_input_label_via_label_for():
    """Returns label text when <label for="id"> matches the element's id."""
    from unittest.mock import MagicMock
    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    element.get_attribute.side_effect = lambda attr: "email-field" if attr == "id" else None
    label_loc = MagicMock()
    label_loc.inner_text.return_value = "Email Address"
    page.locator.return_value = label_loc

    result = _get_input_label(page, element)
    assert result == "Email Address"
    page.locator.assert_called_with('label[for="email-field"]')


def test_get_input_label_via_wrapping_label():
    """Falls back to wrapping ancestor label when label-for lookup fails."""
    from unittest.mock import MagicMock
    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    element.get_attribute.return_value = None
    page.locator.side_effect = Exception("no label[for]")
    ancestor = MagicMock()
    ancestor.inner_text.return_value = "Upload Cover Letter"
    element.locator.return_value = ancestor

    result = _get_input_label(page, element)
    assert result == "Upload Cover Letter"
    element.locator.assert_called_with("xpath=ancestor::label[1]")


def test_get_input_label_via_aria_label():
    """Falls back to aria-label attribute."""
    from unittest.mock import MagicMock
    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    page.locator.side_effect = Exception("no label[for]")
    ancestor = MagicMock()
    ancestor.inner_text.side_effect = Exception("no ancestor")
    element.locator.return_value = ancestor
    element.get_attribute.side_effect = (
        lambda attr: "Cover Letter File" if attr == "aria-label" else None
    )

    result = _get_input_label(page, element)
    assert result == "Cover Letter File"


def test_get_input_label_via_name():
    """Falls back to name attribute when aria-label is absent."""
    from unittest.mock import MagicMock
    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    page.locator.side_effect = Exception("no label[for]")
    ancestor = MagicMock()
    ancestor.inner_text.side_effect = Exception("no ancestor")
    element.locator.return_value = ancestor
    element.get_attribute.side_effect = (
        lambda attr: "cover_letter_upload" if attr == "name" else None
    )

    result = _get_input_label(page, element)
    assert result == "cover_letter_upload"


def test_get_input_label_returns_empty_when_nothing_found():
    """Returns empty string when no label source is available."""
    from unittest.mock import MagicMock
    from worker.tools.field_inspector_tool import _get_input_label

    page = MagicMock()
    element = MagicMock()
    page.locator.side_effect = Exception("no label[for]")
    element.locator.side_effect = Exception("no ancestor")
    element.get_attribute.return_value = None

    result = _get_input_label(page, element)
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_field_inspector_tool.py::test_get_input_label_via_label_for -v
```

Expected: FAIL with `ImportError: cannot import name '_get_input_label'`

- [ ] **Step 3: Add `_get_input_label` to `field_inspector_tool.py`**

At the top of `src/worker/tools/field_inspector_tool.py`, update the imports to include `Locator`:

```python
from playwright.sync_api import Locator, Page, sync_playwright
```

Then add the helper function before `_extract_fields`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_field_inspector_tool.py -k "get_input_label" -v
```

Expected: All 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/worker/tools/field_inspector_tool.py src/worker/tests/tools/test_field_inspector_tool.py
git commit -m "feat: add _get_input_label helper to field_inspector_tool"
```

---

## Task 3: Field Inspector — `job_description` + Label-Aware Classification (TDD)

**Files:**
- Modify: `src/worker/tools/field_inspector_tool.py`
- Modify: `src/worker/tests/tools/test_field_inspector_tool.py`

- [ ] **Step 1: Write failing tests**

Add to `src/worker/tests/tools/test_field_inspector_tool.py`:

```python
def _make_cl_element(aria_label: str):
    """Create a mock Locator whose aria-label attribute returns the given string."""
    el = MagicMock()
    el.get_attribute.side_effect = (
        lambda attr: aria_label if attr == "aria-label" else None
    )
    el.locator.side_effect = Exception("no ancestor")
    return el


def test_requires_cover_letter_true_for_cover_letter_textarea():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    cl_textarea = _make_cl_element("Cover Letter")
    plain_textarea = _make_cl_element("Comments")
    page = MagicMock()

    def locator_side_effect(selector):
        loc = MagicMock()
        if selector == "input[type=file]":
            loc.all.return_value = []
        elif selector.startswith("textarea"):
            loc.all.return_value = [cl_textarea, plain_textarea]
        elif "label" in selector and "[for=" not in selector:
            loc.all.return_value = []
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.evaluate.return_value = "We are hiring an engineer."

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["requires_cover_letter"] is True
    assert data["requires_resume"] is False


def test_requires_cover_letter_true_for_cover_letter_file_input():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    cl_file = _make_cl_element("Cover Letter Upload")
    page = MagicMock()

    def locator_side_effect(selector):
        loc = MagicMock()
        if selector == "input[type=file]":
            loc.all.return_value = [cl_file]
        elif selector.startswith("textarea"):
            loc.all.return_value = []
        elif "label" in selector and "[for=" not in selector:
            loc.all.return_value = []
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.evaluate.return_value = "Job description text."

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["requires_cover_letter"] is True
    assert data["requires_resume"] is False  # CL file input does NOT set requires_resume


def test_requires_resume_true_only_for_non_cover_letter_file_input():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    resume_file = _make_cl_element("Resume Upload")
    cl_file = _make_cl_element("Cover Letter")
    page = MagicMock()

    def locator_side_effect(selector):
        loc = MagicMock()
        if selector == "input[type=file]":
            loc.all.return_value = [resume_file, cl_file]
        elif selector.startswith("textarea"):
            loc.all.return_value = []
        elif "label" in selector and "[for=" not in selector:
            loc.all.return_value = []
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.evaluate.return_value = "Job description."

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["requires_resume"] is True
    assert data["requires_cover_letter"] is True


def test_job_description_extracted_and_trimmed():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    page = MagicMock()
    long_text = "A" * 5000
    page.evaluate.return_value = long_text

    def locator_side_effect(selector):
        loc = MagicMock()
        loc.all.return_value = []
        loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert len(data["job_description"]) == 4000
    assert data["job_description"] == "A" * 4000


def test_error_path_includes_new_fields():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.side_effect = Exception("browser crashed")
        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["requires_cover_letter"] is False
    assert data["job_description"] == ""
    assert "error" in data
```

Note: add `from unittest.mock import patch` to the test file imports if not already present.

- [ ] **Step 2: Run tests to verify they fail**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_field_inspector_tool.py::test_job_description_extracted_and_trimmed -v
```

Expected: FAIL (KeyError: 'job_description')

- [ ] **Step 3: Update `_inspector_work` in `field_inspector_tool.py`**

Replace the `_inspector_work` function body. The key section is inside the `try` block (after `click_through_to_form(page)` and before `browser.close()`). Replace the current field extraction and `requires_resume` lines with:

```python
            try:
                fields = _extract_fields(page)

                # Extract visible page text for cover letter context
                raw_text = page.evaluate("document.body.innerText") or ""
                job_description = raw_text[:4000]

                # Label-aware classification of file inputs and textareas
                requires_resume = False
                requires_cover_letter = False
                for file_input in page.locator("input[type=file]").all():
                    label_text = _get_input_label(page, file_input).lower()
                    if "cover letter" in label_text:
                        requires_cover_letter = True
                    else:
                        requires_resume = True
                for textarea in page.locator("textarea").all():
                    label_text = _get_input_label(page, textarea).lower()
                    if "cover letter" in label_text:
                        requires_cover_letter = True
            finally:
                browser.close()

        result = {
            "url": url,
            "form_fields": fields,
            "requires_resume": requires_resume,
            "requires_cover_letter": requires_cover_letter,
            "job_description": job_description,
        }
        logger.info(
            "fields_extracted",
            url=url,
            field_count=len(fields),
            requires_cover_letter=requires_cover_letter,
        )
        return json.dumps(result)
```

- [ ] **Step 4: Update all error paths in `field_inspector_tool.py`**

Three error JSON objects need `requires_cover_letter` and `job_description`. Update each:

In `_inspector_work` exception handler (line ~113):
```python
    except Exception as exc:
        logger.error("field_inspection_failed", url=url, error=str(exc))
        return json.dumps(
            {
                "url": url,
                "form_fields": [],
                "requires_resume": False,
                "requires_cover_letter": False,
                "job_description": "",
                "error": str(exc),
            }
        )
```

In `field_inspector_tool` TimeoutError handler:
```python
            return json.dumps(
                {
                    "url": url,
                    "form_fields": [],
                    "requires_resume": False,
                    "requires_cover_letter": False,
                    "job_description": "",
                    "error": "Field inspection timed out after 90 seconds",
                }
            )
```

In `field_inspector_tool` general Exception handler:
```python
            return json.dumps(
                {
                    "url": url,
                    "form_fields": [],
                    "requires_resume": False,
                    "requires_cover_letter": False,
                    "job_description": "",
                    "error": f"Inspector execution error: {exc}",
                }
            )
```

- [ ] **Step 5: Run all field inspector tests**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_field_inspector_tool.py -v
```

Expected: All PASS. The existing `test_tool_returns_json_with_form_fields` will fail because it asserts `data["requires_resume"] is True` based on `file_inputs=1` — update that test to use a labeled element and also check for the new fields:

```python
def test_tool_returns_json_with_form_fields():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    resume_file = _make_cl_element("Resume")
    page = _make_page(labels=["First Name", "Email"])

    def locator_side_effect(selector):
        loc = MagicMock()
        if "label" in selector and "[for=" not in selector:
            loc.all.return_value = [_mock_element(text="First Name"), _mock_element(text="Email")]
        elif selector == "input[type=file]":
            loc.all.return_value = [resume_file]
        elif selector.startswith("input"):
            loc.all.return_value = []
        elif selector.startswith("textarea"):
            loc.all.return_value = []
        elif selector.startswith("select"):
            loc.all.return_value = []
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.evaluate.return_value = "Job description text here."

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert "First Name" in data["form_fields"]
    assert "Email" in data["form_fields"]
    assert data["requires_resume"] is True
    assert data["requires_cover_letter"] is False
    assert data["url"] == "https://example.com"
    assert "job_description" in data
```

Also update `test_tool_returns_empty_on_playwright_error` to check for new fields:

```python
def test_tool_returns_empty_on_playwright_error():
    from worker.tools.field_inspector_tool import field_inspector_tool
    import json

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.side_effect = Exception("browser crashed")
        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["form_fields"] == []
    assert data["requires_resume"] is False
    assert data["requires_cover_letter"] is False
    assert data["job_description"] == ""
    assert "error" in data
```

Run again: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/worker/tools/field_inspector_tool.py src/worker/tests/tools/test_field_inspector_tool.py
git commit -m "feat: extend field_inspector_tool with job_description and cover letter detection"
```

---

## Task 4: Settings + `_TASK_INSPECT_DESCRIPTION`

**Files:**
- Modify: `src/worker/config.py`
- Modify: `src/worker/crew.py`
- Modify: `src/worker/tests/test_config.py`

- [ ] **Step 1: Write failing settings test**

Add to `src/worker/tests/test_config.py`:

```python
    def test_default_cover_letter_context_path(self, required_env: None) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.cover_letter_context_path == Path(
            "./worker/personal/cover_letter_context.md"
        )

    def test_default_cover_letter_output_dir(self, required_env: None) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.cover_letter_output_dir == Path("./worker/personal/cover_letters")
```

- [ ] **Step 2: Run to verify failure**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/test_config.py::TestSettingsDefaults::test_default_cover_letter_context_path -v
```

Expected: FAIL

- [ ] **Step 3: Add settings fields to `config.py`**

In `src/worker/config.py`, inside the `Settings` class after `personal_data_path`:

```python
    # Cover letter
    cover_letter_context_path: Path = Path("./worker/personal/cover_letter_context.md")
    cover_letter_output_dir: Path = Path("./worker/personal/cover_letters")
```

- [ ] **Step 4: Update `_TASK_INSPECT_DESCRIPTION` in `crew.py`**

In `src/worker/crew.py`, find `_TASK_INSPECT_DESCRIPTION` and update `expected_output` reference in `task_inspect` to include the new fields. The task description also needs to instruct the agent about the new output fields. Update the task description string:

```python
_TASK_INSPECT_DESCRIPTION = (
    "You have a list of job listings from the Searcher. "
    "Each listing is a block starting with 'JOB:' and containing a 'URL:' line.\n\n"
    "IMPORTANT: If the input contains no lines starting with 'URL:', "
    "output an empty InspectedJobs list immediately without calling any tools.\n\n"
    "For EACH job block, call the Field Inspector tool exactly once with its URL.\n"
    "Do NOT skip any job. Do NOT call the tool more than once per URL.\n"
    "Collect all results and output them as an InspectedJobs object with the "
    "form_fields, requires_resume, requires_cover_letter, and job_description values "
    "returned by the tool for each job."
)
```

Also update the `task_inspect` expected output in `run_crew`:

```python
    task_inspect = Task(
        description=_TASK_INSPECT_DESCRIPTION,
        expected_output=(
            "InspectedJobs JSON with form_fields, requires_resume, requires_cover_letter, "
            "and job_description for the job."
        ),
        agent=field_inspector,
        output_pydantic=InspectedJobs,
    )
```

- [ ] **Step 5: Run tests**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/test_config.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/worker/config.py src/worker/crew.py src/worker/tests/test_config.py
git commit -m "feat: add cover letter settings and update inspect task description"
```

---

## Task 5: `cover_letter_context_loader_tool` (TDD)

**Files:**
- Create: `src/worker/tools/cover_letter_context_loader.py`
- Create: `src/worker/tests/tools/test_cover_letter_tools.py`

- [ ] **Step 1: Write failing tests**

Create `src/worker/tests/tools/test_cover_letter_tools.py`:

```python
"""Tests for cover letter tools: context loader and PDF renderer."""

from pathlib import Path
from unittest.mock import patch


# ── Context Loader ────────────────────────────────────────────────────────────


def test_context_loader_returns_empty_string_when_file_missing(tmp_path):
    """Returns '' and logs a warning when the context file does not exist."""
    from worker.tools.cover_letter_context_loader import cover_letter_context_loader_tool

    missing_path = tmp_path / "cover_letter_context.md"

    with patch("worker.tools.cover_letter_context_loader.settings") as mock_settings:
        mock_settings.cover_letter_context_path = missing_path
        result = cover_letter_context_loader_tool.run()

    assert result == ""


def test_context_loader_returns_empty_string_for_empty_file(tmp_path):
    """Returns '' for a file that exists but has no content."""
    from worker.tools.cover_letter_context_loader import cover_letter_context_loader_tool

    empty_file = tmp_path / "cover_letter_context.md"
    empty_file.write_text("")

    with patch("worker.tools.cover_letter_context_loader.settings") as mock_settings:
        mock_settings.cover_letter_context_path = empty_file
        result = cover_letter_context_loader_tool.run()

    assert result == ""


def test_context_loader_returns_file_content(tmp_path):
    """Returns the file contents when the file exists and has content."""
    from worker.tools.cover_letter_context_loader import cover_letter_context_loader_tool

    context_file = tmp_path / "cover_letter_context.md"
    context_file.write_text("I am passionate about distributed systems and Python.")

    with patch("worker.tools.cover_letter_context_loader.settings") as mock_settings:
        mock_settings.cover_letter_context_path = context_file
        result = cover_letter_context_loader_tool.run()

    assert result == "I am passionate about distributed systems and Python."
```

- [ ] **Step 2: Run to verify failure**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_cover_letter_tools.py::test_context_loader_returns_empty_string_when_file_missing -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Create the tool**

Create `src/worker/tools/cover_letter_context_loader.py`:

```python
from crewai.tools import tool

from worker.config import settings
from worker.logging_config import get_logger

logger = get_logger(__name__)


@tool("Cover Letter Context Loader")
def cover_letter_context_loader_tool() -> str:
    """Load the user's cover letter context file (tone, narrative, background).

    Returns the file contents, or an empty string if the file does not exist.
    """
    path = settings.cover_letter_context_path
    if not path.exists():
        logger.warning("cover_letter_context_not_found", path=str(path))
        return ""
    return path.read_text().strip()
```

- [ ] **Step 4: Run tests**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_cover_letter_tools.py -k "context_loader" -v
```

Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/worker/tools/cover_letter_context_loader.py src/worker/tests/tools/test_cover_letter_tools.py
git commit -m "feat: add cover_letter_context_loader_tool"
```

---

## Task 6: `pdf_renderer_tool` (TDD)

**Files:**
- Create: `src/worker/tools/cover_letter_renderer.py`
- Modify: `src/worker/tests/tools/test_cover_letter_tools.py`

- [ ] **Step 1: Install `reportlab`**

```bash
uv add reportlab
```

Expected: `reportlab` added to `pyproject.toml` and `uv.lock`.

- [ ] **Step 2: Write failing tests**

Add to `src/worker/tests/tools/test_cover_letter_tools.py`:

```python
# ── PDF Renderer ──────────────────────────────────────────────────────────────


def test_pdf_renderer_sanitizes_filename(tmp_path):
    """Company and job title are sanitized to lowercase_with_underscores."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="Acme Corp!", job_title="Senior Engineer", cover_letter_text="Dear Hiring Manager,"
        )

    assert result.startswith(str(tmp_path))
    filename = Path(result).name
    assert filename.startswith("acme_corp_senior_engineer_")
    assert filename.endswith(".pdf")


def test_pdf_renderer_empty_company_uses_fallback(tmp_path):
    """Empty company string after sanitization falls back to 'unknown_company'."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="@#$%", job_title="Engineer", cover_letter_text="Hello."
        )

    assert not result.startswith("Error:")
    assert "unknown_company" in Path(result).name


def test_pdf_renderer_empty_job_title_uses_fallback(tmp_path):
    """Empty job title after sanitization falls back to 'unknown_role'."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="Acme", job_title="---", cover_letter_text="Hello."
        )

    assert not result.startswith("Error:")
    assert "unknown_role" in Path(result).name


def test_pdf_renderer_creates_output_dir(tmp_path):
    """Creates the output directory if it does not exist."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    new_dir = tmp_path / "letters" / "nested"
    assert not new_dir.exists()

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = new_dir
        result = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Hello."
        )

    assert new_dir.exists()
    assert not result.startswith("Error:")


def test_pdf_renderer_two_calls_produce_different_filenames(tmp_path):
    """Timestamp suffix ensures two calls don't overwrite each other."""
    import time
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result1 = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Letter 1."
        )
        time.sleep(1.1)  # ensure different second
        result2 = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Letter 2."
        )

    assert result1 != result2
    assert Path(result1).exists()
    assert Path(result2).exists()


def test_pdf_renderer_returns_absolute_path(tmp_path):
    """Returned path is absolute (resolve() applied)."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Hello."
        )

    assert Path(result).is_absolute()
    assert Path(result).exists()


def test_pdf_renderer_returns_error_string_on_bad_path():
    """Returns 'Error: ...' when the output path is unwritable."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    unwritable = Path("/root/no_permission_here")

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = unwritable
        result = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Hello."
        )

    assert result.startswith("Error:")
```

- [ ] **Step 3: Run to verify failure**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_cover_letter_tools.py::test_pdf_renderer_sanitizes_filename -v
```

Expected: FAIL (ImportError)

- [ ] **Step 4: Create the tool**

Create `src/worker/tools/cover_letter_renderer.py`:

```python
import re
from datetime import datetime
from pathlib import Path

from crewai.tools import tool
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate

from worker.config import settings
from worker.logging_config import get_logger

logger = get_logger(__name__)


def _sanitize(text: str, fallback: str) -> str:
    """Lowercase, strip non-alphanumeric-or-space chars, replace spaces with underscores."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", text).strip()
    cleaned = re.sub(r"\s+", "_", cleaned).lower()
    return cleaned if cleaned else fallback


@tool("Cover Letter PDF Renderer")
def pdf_renderer_tool(company: str, job_title: str, cover_letter_text: str) -> str:
    """Render a cover letter to a PDF file and return its absolute path.

    Returns the absolute path string on success, or 'Error: ...' on any failure.
    """
    try:
        safe_company = _sanitize(company, "unknown_company")
        safe_title = _sanitize(job_title, "unknown_role")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_company}_{safe_title}_{timestamp}.pdf"

        output_dir = settings.cover_letter_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / filename).resolve()

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=inch,
            rightMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        story = []
        for line in cover_letter_text.split("\n"):
            story.append(Paragraph(line if line.strip() else "&nbsp;", styles["Normal"]))
        doc.build(story)

        logger.info("cover_letter_rendered", path=str(output_path))
        return str(output_path)

    except Exception as exc:
        logger.error("cover_letter_render_failed", error=str(exc))
        return f"Error: {exc}"
```

- [ ] **Step 5: Run tests**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_cover_letter_tools.py -k "pdf_renderer" -v
```

Expected: All 7 PASS

- [ ] **Step 6: Commit**

```bash
git add src/worker/tools/cover_letter_renderer.py src/worker/tests/tools/test_cover_letter_tools.py \
  pyproject.toml uv.lock
git commit -m "feat: add pdf_renderer_tool using reportlab"
```

---

## Task 7: `cover_letter_writer` Agent (TDD)

**Files:**
- Create: `src/worker/agents/cover_letter_writer.py`
- Modify: `src/worker/tests/models/test_crew_models.py`

- [ ] **Step 1: Write failing build test**

Add to `src/worker/tests/models/test_crew_models.py`:

```python
def test_build_cover_letter_writer_returns_agent():
    from unittest.mock import MagicMock, patch

    with (
        patch("worker.agents.cover_letter_writer.build_llm") as mock_llm,
        patch("worker.agents.cover_letter_writer.resume_loader_tool"),
        patch("worker.agents.cover_letter_writer.cover_letter_context_loader_tool"),
        patch("worker.agents.cover_letter_writer.pdf_renderer_tool"),
        patch("worker.agents.cover_letter_writer.Agent") as mock_agent,
    ):
        mock_llm.return_value = MagicMock()
        agent_instance = MagicMock()
        agent_instance.role = "Cover Letter Writer"
        agent_instance.allow_delegation = False
        mock_agent.return_value = agent_instance

        from worker.agents.cover_letter_writer import build_cover_letter_writer

        agent = build_cover_letter_writer()

    assert agent.role == "Cover Letter Writer"
    assert agent.allow_delegation is False
```

- [ ] **Step 2: Run to verify failure**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/models/test_crew_models.py::test_build_cover_letter_writer_returns_agent -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Create the agent**

Create `src/worker/agents/cover_letter_writer.py`:

```python
from crewai import Agent

from worker.config import build_llm, settings
from worker.tools.cover_letter_context_loader import cover_letter_context_loader_tool
from worker.tools.cover_letter_renderer import pdf_renderer_tool
from worker.tools.resume_loader import resume_loader_tool


def build_cover_letter_writer() -> Agent:
    """Build the Cover Letter Writer agent."""
    llm = build_llm(settings.reasoning_model)
    return Agent(
        role="Cover Letter Writer",
        goal=(
            "Draft a tailored, compelling cover letter for each job application that requires one."
        ),
        backstory=(
            "You read the applicant's resume and personal background context, then craft a "
            "personalized cover letter for the specific job. You always assign cover_letter_text "
            "before calling the PDF renderer. If PDF rendering fails (result starts with 'Error:'), "
            "you set cover_letter_path to null but keep cover_letter_text populated."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[resume_loader_tool, cover_letter_context_loader_tool, pdf_renderer_tool],
        llm=llm,
    )
```

- [ ] **Step 4: Run the test**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/models/test_crew_models.py::test_build_cover_letter_writer_returns_agent -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/worker/agents/cover_letter_writer.py src/worker/tests/models/test_crew_models.py
git commit -m "feat: add build_cover_letter_writer agent"
```

---

## Task 8: Browser Tool Updates (TDD)

**Files:**
- Modify: `src/worker/tools/browser_tool.py`
- Modify: `src/worker/tests/tools/test_browser_tool.py`

- [ ] **Step 1: Write failing tests**

Add to `src/worker/tests/tools/test_browser_tool.py`:

```python
def _make_labeled_element(aria_label: str) -> MagicMock:
    """Mock Locator whose aria-label attribute returns the given string."""
    el = MagicMock()
    el.get_attribute.side_effect = (
        lambda attr: aria_label if attr == "aria-label" else None
    )
    el.locator.side_effect = Exception("no ancestor")
    return el


def _make_page_with_cl_textarea(submit_count: int = 1) -> tuple[MagicMock, MagicMock]:
    """Page with a cover-letter-labeled textarea. Returns (page, textarea_mock)."""
    page = MagicMock()
    cl_textarea = _make_labeled_element("Cover Letter")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = submit_count
        elif "textarea" in selector:
            loc.all.return_value = [cl_textarea]
        elif "input[type='file']" in selector or "input[type=file]" in selector:
            loc.all.return_value = []
            loc.count.return_value = 0
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()
    return page, cl_textarea


def _make_page_with_cl_file_input(
    submit_count: int = 1,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Page with a resume file input and a cover-letter file input."""
    page = MagicMock()
    resume_fi = _make_labeled_element("Resume")
    cl_fi = _make_labeled_element("Cover Letter")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = submit_count
        elif "textarea" in selector:
            loc.all.return_value = []
        elif "input[type='file']" in selector or "input[type=file]" in selector:
            loc.all.return_value = [resume_fi, cl_fi]
            loc.count.return_value = 2
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()
    return page, resume_fi, cl_fi


def test_browser_uploads_resume_to_non_cl_file_input_only(tmp_path):
    """Resume is uploaded to the non-cover-letter file input, not the CL one."""
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"dummy")

    page, resume_fi, cl_fi = _make_page_with_cl_file_input()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = resume_file
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work
        _browser_work("https://example.com", "{}", requires_resume=True)

    resume_fi.set_input_files.assert_called_once_with(str(resume_file))
    cl_fi.set_input_files.assert_not_called()


def test_browser_pastes_cover_letter_text_into_textarea(tmp_path):
    """cover_letter_text is pasted into a cover-letter-labeled textarea."""
    page, cl_textarea = _make_page_with_cl_textarea()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work
        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_text="Dear Hiring Manager,\n\nI am excited...",
        )

    cl_textarea.fill.assert_called_once_with(
        "Dear Hiring Manager,\n\nI am excited..."
    )


def test_browser_uploads_cl_file_when_path_set(tmp_path):
    """cover_letter_path is uploaded when a CL file input is present."""
    cl_pdf = tmp_path / "cover_letter.pdf"
    cl_pdf.write_bytes(b"pdf content")

    page, resume_fi, cl_fi = _make_page_with_cl_file_input()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work
        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_path=str(cl_pdf),
        )

    cl_fi.set_input_files.assert_called_once_with(str(cl_pdf))


def test_browser_skips_cl_file_when_path_is_none_and_no_textarea(tmp_path):
    """No action on CL file input when cover_letter_path is None and no text area."""
    page, resume_fi, cl_fi = _make_page_with_cl_file_input()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work
        result = _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_path=None,
            cover_letter_text=None,
        )

    cl_fi.set_input_files.assert_not_called()


def test_browser_uses_file_upload_not_textarea_when_path_set(tmp_path):
    """When both CL file input and textarea exist and path is set, file upload wins."""
    cl_pdf = tmp_path / "cl.pdf"
    cl_pdf.write_bytes(b"pdf")

    page = MagicMock()
    cl_fi = _make_labeled_element("Cover Letter")
    cl_textarea = _make_labeled_element("Cover Letter")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector.lower() or "apply" in selector.lower():
            loc.count.return_value = 1
        elif "textarea" in selector:
            loc.all.return_value = [cl_textarea]
        elif "input[type='file']" in selector or "input[type=file]" in selector:
            loc.all.return_value = [cl_fi]
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_text.return_value = MagicMock()
    page.get_by_text.return_value.locator.return_value = MagicMock()

    with (
        patch("worker.tools.browser_tool.sync_playwright", _patch_playwright(page)),
        patch("worker.tools.browser_tool.click_through_to_form"),
        patch("worker.tools.browser_tool._record_application"),
        patch("worker.tools.browser_tool.settings") as mock_settings,
    ):
        mock_settings.resume_path = tmp_path / "resume.pdf"
        mock_settings.headless = True
        from worker.tools.browser_tool import _browser_work
        _browser_work(
            "https://example.com",
            "{}",
            requires_resume=False,
            cover_letter_path=str(cl_pdf),
            cover_letter_text="Dear Hiring Manager...",
        )

    cl_fi.set_input_files.assert_called_once_with(str(cl_pdf))
    cl_textarea.fill.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_browser_tool.py::test_browser_pastes_cover_letter_text_into_textarea -v
```

Expected: FAIL (TypeError: `_browser_work` takes 3 positional arguments)

- [ ] **Step 3: Add `_get_file_input_label` and `_fill_cover_letter` helpers to `browser_tool.py`**

Add after the `_load_personal_data` function in `src/worker/tools/browser_tool.py`:

```python
def _get_file_input_label(page, element) -> str:
    """Four-step label lookup for a form element (same logic as field_inspector_tool)."""
    with contextlib.suppress(Exception):
        el_id = element.get_attribute("id")
        if el_id:
            text = page.locator(f'label[for="{el_id}"]').inner_text()
            if text.strip():
                return text.strip()
    with contextlib.suppress(Exception):
        text = element.locator("xpath=ancestor::label[1]").inner_text()
        if text.strip():
            return text.strip()
    with contextlib.suppress(Exception):
        text = element.get_attribute("aria-label") or ""
        if text.strip():
            return text.strip()
    with contextlib.suppress(Exception):
        text = element.get_attribute("name") or ""
        if text.strip():
            return text.strip()
    return ""


def _fill_cover_letter(
    page,
    cover_letter_text: str | None,
    cover_letter_path: str | None,
    url: str,
) -> None:
    """Fill cover letter fields on the form if present."""
    cl_file_inputs = []
    cl_textareas = []

    for fi in page.locator("input[type='file']").all():
        with contextlib.suppress(Exception):
            if "cover letter" in _get_file_input_label(page, fi).lower():
                cl_file_inputs.append(fi)

    for ta in page.locator("textarea").all():
        with contextlib.suppress(Exception):
            if "cover letter" in _get_file_input_label(page, ta).lower():
                cl_textareas.append(ta)

    if not cl_file_inputs and not cl_textareas:
        return  # no cover letter fields detected

    file_uploaded = False
    if cl_file_inputs and cover_letter_path is not None:
        with contextlib.suppress(Exception):
            cl_file_inputs[0].set_input_files(cover_letter_path)
            logger.info("cover_letter_file_uploaded", url=url, path=cover_letter_path)
            file_uploaded = True

    if not file_uploaded:
        if cl_textareas:
            if cover_letter_text is not None:
                with contextlib.suppress(Exception):
                    cl_textareas[0].fill(cover_letter_text)
                    logger.info("cover_letter_pasted", url=url)
            else:
                logger.warning("cover_letter_text_missing", url=url)
        elif cl_file_inputs:
            logger.warning("cover_letter_path_missing", url=url)
```

- [ ] **Step 4: Update `_browser_work` signature and resume upload logic**

Update `_browser_work` signature:

```python
def _browser_work(
    url: str,
    json_instructions: str,
    requires_resume: bool,
    cover_letter_text: str | None = None,
    cover_letter_path: str | None = None,
) -> str:
```

Replace the existing resume upload block (the `if requires_resume:` section) with label-aware logic:

```python
            # Upload resume (skip file inputs labeled "cover letter")
            if requires_resume:
                if resume_path.exists():
                    logger.info("uploading_resume", path=str(resume_path))
                    for fi in page.locator("input[type='file']").all():
                        with contextlib.suppress(Exception):
                            label = _get_file_input_label(page, fi).lower()
                            if "cover letter" not in label:
                                fi.set_input_files(str(resume_path))
                                break
                else:
                    logger.error("resume_not_found", path=str(resume_path))

            # Fill cover letter fields
            _fill_cover_letter(page, cover_letter_text, cover_letter_path, url)
```

Update `browser_tool` signature and the `pool.submit` call:

```python
@tool("Browser Form Fitter")
def browser_tool(
    url: str,
    json_instructions: str,
    requires_resume: bool,
    cover_letter_text: str | None = None,
    cover_letter_path: str | None = None,
) -> str:
    """Navigate to a job application URL, fill form fields, upload resume, and submit.

    Runs all Playwright operations in a ThreadPoolExecutor so they are isolated
    from CrewAI's asyncio event loop (sync_playwright cannot run inside a loop).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _browser_work, url, json_instructions, requires_resume,
            cover_letter_text, cover_letter_path,
        )
```

Also update the `_record_application` call in the timeout/error handlers to keep signature consistency (no changes needed to those — they only use `url`, `requires_resume`, `status`, `error`).

- [ ] **Step 5: Run browser tool tests**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/tools/test_browser_tool.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/worker/tools/browser_tool.py src/worker/tests/tools/test_browser_tool.py
git commit -m "feat: update browser_tool with label-aware resume upload and cover letter fill logic"
```

---

## Task 9: `crew.py` Pipeline Changes (TDD)

**Files:**
- Modify: `src/worker/crew.py`
- Modify: `src/worker/tests/test_crew.py`

- [ ] **Step 1: Write failing tests**

Add to `src/worker/tests/test_crew.py`:

```python
def test_crew_has_five_tasks_in_normal_mode(tmp_path):
    """Non-dry-run crew must include exactly 5 tasks (including Cover Letter Writer)."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text('{"First Name": "Tanner"}')

    tasks_passed = []

    def capture_crew(**kwargs):
        tasks_passed.extend(kwargs.get("tasks", []))
        instance = MagicMock()
        instance.kickoff.return_value = MagicMock(__str__=lambda self: "done")
        return instance

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(crew_module, "build_cover_letter_writer", return_value=MagicMock()),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Task", return_value=MagicMock()),
        patch.object(crew_module, "Crew", side_effect=capture_crew),
        patch.object(crew_module, "set_current_task_id"),
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
        )
        crew_module.run_crew(criteria)

    assert len(tasks_passed) == 5


def test_crew_dry_run_has_three_tasks_and_excludes_cover_letter_writer(tmp_path):
    """dry_run=True crew must have exactly 3 tasks (no CL writer, no Browser)."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text('{"First Name": "Tanner"}')

    tasks_passed = []

    def capture_crew(**kwargs):
        tasks_passed.extend(kwargs.get("tasks", []))
        mock_task_eval = MagicMock()
        mock_task_eval.output.pydantic = MagicMock()
        instance = MagicMock()
        instance.kickoff.return_value = MagicMock()
        return instance

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(crew_module, "build_cover_letter_writer", return_value=MagicMock()),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Task", return_value=MagicMock()),
        patch.object(crew_module, "Crew", side_effect=capture_crew),
        patch.object(crew_module, "set_current_task_id"),
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer",
            location="Remote",
            min_salary=100000,
            job_keywords=["Python"],
        )
        crew_module.run_crew(criteria, dry_run=True)

    assert len(tasks_passed) == 3
```

- [ ] **Step 2: Run to verify failure**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/test_crew.py::test_crew_has_five_tasks_in_normal_mode -v
```

Expected: FAIL (`build_cover_letter_writer` not imported)

- [ ] **Step 3: Update `crew.py` imports and task description**

At the top of `src/worker/crew.py`, add the import:

```python
from worker.agents.cover_letter_writer import build_cover_letter_writer
```

Add the task description constant after `_TASK_APPLY_DESCRIPTION`:

```python
_TASK_COVER_LETTER_DESCRIPTION = (
    "You will receive two sources of data:\n"
    "- Your sequential task input contains the ApplicationPackets produced by the Evaluator.\n"
    "- Your context contains the InspectedJobs produced by the Field Inspector "
    "(which includes job_description for each URL).\n\n"
    "STEP 1: Call resume_loader_tool and cover_letter_context_loader_tool ONCE at the start. "
    "Reuse the results for all packets.\n\n"
    "STEP 2: For each packet where requires_cover_letter=True:\n"
    "  a. Find the InspectedJob where InspectedJob.url == ApplicationPacket.url. "
    "If no match is found, use an empty job_description and continue — do not halt.\n"
    "  b. Draft a compelling, tailored cover letter using: job_title, company, "
    "job_description, resume text, and personal context.\n"
    "  c. Set cover_letter_text to the drafted letter text BEFORE calling pdf_renderer_tool.\n"
    "  d. Call pdf_renderer_tool with company, job_title, and cover_letter_text.\n"
    "  e. If the returned string starts with 'Error:', set cover_letter_path=null and continue.\n"
    "     Otherwise, set cover_letter_path to the returned absolute path.\n\n"
    "STEP 3: For packets where requires_cover_letter=False: "
    "set cover_letter_text=null and cover_letter_path=null.\n\n"
    "Output the complete ApplicationPackets JSON including ALL packets."
)
```

Update `_TASK_APPLY_DESCRIPTION` to include cover letter params:

```python
_TASK_APPLY_DESCRIPTION = (
    "You have a list of ApplicationPackets from the Cover Letter Writer. "
    "For EACH packet, immediately call the Browser Form Fitter tool with:\n"
    "- url: the exact URL from the packet\n"
    "- json_instructions: the exact json_instructions string from the packet\n"
    "- requires_resume: the boolean value from the packet\n"
    "- cover_letter_text: the cover_letter_text value from the packet (may be null)\n"
    "- cover_letter_path: the cover_letter_path value from the packet (may be null)\n"
    "Do NOT search the web. Do NOT skip any packets. Call Browser Form Fitter once per job."
)
```

- [ ] **Step 4: Update `run_crew` to insert Cover Letter Writer**

In `run_crew`, update the `else` branch (non-dry-run) and keep dry-run untouched:

```python
    if dry_run:
        agents = [searcher, field_inspector, evaluator]
        tasks = [task_search, task_inspect, task_evaluate]
    else:
        cover_letter_writer_agent = build_cover_letter_writer()
        browser_agent = build_browser()

        task_cover_letter = Task(
            description=_TASK_COVER_LETTER_DESCRIPTION,
            expected_output=(
                "ApplicationPackets JSON identical to the input, with cover_letter_text and "
                "cover_letter_path populated for each packet that had requires_cover_letter=True. "
                "If PDF rendering failed, cover_letter_path must be null but cover_letter_text "
                "must still be set. Packets with requires_cover_letter=False are passed through "
                "with cover_letter_text=null and cover_letter_path=null."
            ),
            agent=cover_letter_writer_agent,
            output_pydantic=ApplicationPackets,
            context=[task_inspect],
        )
        task_apply = Task(
            description=_TASK_APPLY_DESCRIPTION,
            expected_output="Final report confirming the application was submitted.",
            agent=browser_agent,
        )
        agents = [searcher, field_inspector, evaluator, cover_letter_writer_agent, browser_agent]
        tasks = [task_search, task_inspect, task_evaluate, task_cover_letter, task_apply]
```

The `company` extraction at the end of `run_crew` (non-dry-run path) should now read from `task_cover_letter.output.pydantic` since that is the last task before Browser. Update:

```python
    # Extract the company that was evaluated so the caller can exclude it next round.
    company: str | None = None
    try:
        packets = task_cover_letter.output.pydantic  # type: ignore[assignment, union-attr]
        if packets and packets.job_applications:
            company = packets.job_applications[0].company
    except Exception:
        pass
```

Note: `task_cover_letter` is only defined in the `else` branch. Move the `company` extraction into the `else` branch accordingly to avoid a `NameError` in dry-run. The dry-run path is unchanged.

The existing `test_crew_has_four_tasks` test will now fail — update it to expect 5:

```python
def test_crew_has_five_tasks(tmp_path):
    """Crew must be built with exactly 5 tasks."""
    ...
    assert len(tasks_passed) == 5
```

- [ ] **Step 5: Run all crew tests**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/test_crew.py -v
```

Expected: All PASS

- [ ] **Step 6: Run full test suite**

```bash
SUPABASE_URL=https://placeholder.supabase.co SUPABASE_KEY=placeholder SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/ -x -q
```

Expected: All PASS

- [ ] **Step 7: Run pre-push checks**

```bash
uv run ruff check . --fix && \
uv run ruff format . && \
uv run mypy src/worker/ && \
SUPABASE_URL=https://placeholder.supabase.co \
SUPABASE_KEY=placeholder \
SUPABASE_SERVICE_ROLE_KEY=placeholder \
uv run pytest src/worker/tests/ -x -q
```

Expected: All checks pass, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/worker/crew.py src/worker/tests/test_crew.py
git commit -m "feat: insert CoverLetterWriter into crew pipeline between Evaluator and Browser"
```
