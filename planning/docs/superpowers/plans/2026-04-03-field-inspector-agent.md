# Field Inspector Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Field Inspector agent to the CrewAI pipeline that visits each job URL with Playwright and extracts actual form field labels, so the Evaluator can map real fields to personal data instead of guessing.

**Architecture:** 4-stage sequential pipeline — Searcher → Field Inspector → Evaluator → Browser. Each of the first 3 stages produces a typed Pydantic object via CrewAI's `output_pydantic` task parameter. Personal data is loaded from `worker/personal/personal_data.json` in `run_crew()` and injected into the Evaluator task as a template variable.

**Tech Stack:** Python 3.12, CrewAI 1.12.2, Playwright (sync API), Pydantic v2, pytest, pytest-mock

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `worker/models/job_listing.py` | Create | `JobListing` + `SearchResults` Pydantic models |
| `worker/models/inspected_job.py` | Create | `InspectedJob` + `InspectedJobs` Pydantic models |
| `worker/models/application_packet.py` | Create | `ApplicationPacket` + `ApplicationPackets` Pydantic models |
| `worker/tools/field_inspector_tool.py` | Create | Playwright DOM extraction tool |
| `worker/agents/field_inspector.py` | Create | `build_field_inspector()` factory |
| `worker/crew.py` | Modify | Wire 4-task pipeline, inject personal_data |
| `worker/tests/__init__.py` | Create | Make worker/tests a package |
| `worker/tests/models/__init__.py` | Create | Make sub-package |
| `worker/tests/models/test_crew_models.py` | Create | Model unit tests |
| `worker/tests/tools/__init__.py` | Create | Make sub-package |
| `worker/tests/tools/test_field_inspector_tool.py` | Create | Tool unit tests with mocked Playwright |

---

## Task 1: Pydantic Models

**Files:**
- Create: `worker/models/job_listing.py`
- Create: `worker/models/inspected_job.py`
- Create: `worker/models/application_packet.py`
- Create: `worker/tests/__init__.py`
- Create: `worker/tests/models/__init__.py`
- Create: `worker/tests/models/test_crew_models.py`

- [ ] **Step 1: Write the failing tests**

Create `worker/tests/__init__.py` (empty) and `worker/tests/models/__init__.py` (empty), then create `worker/tests/models/test_crew_models.py`:

```python
import pytest
from pydantic import ValidationError


def test_job_listing_requires_url_company_title():
    from worker.models.job_listing import JobListing
    job = JobListing(url="https://example.com", company="Acme", job_title="Engineer")
    assert job.url == "https://example.com"
    assert job.company == "Acme"
    assert job.job_title == "Engineer"


def test_search_results_holds_job_list():
    from worker.models.job_listing import JobListing, SearchResults
    results = SearchResults(jobs=[
        JobListing(url="https://a.com", company="A", job_title="Dev"),
        JobListing(url="https://b.com", company="B", job_title="Eng"),
    ])
    assert len(results.jobs) == 2


def test_search_results_empty_jobs_allowed():
    from worker.models.job_listing import SearchResults
    results = SearchResults(jobs=[])
    assert results.jobs == []


def test_inspected_job_fields_and_resume():
    from worker.models.inspected_job import InspectedJob
    job = InspectedJob(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        form_fields=["First Name", "Email"],
        requires_resume=True,
    )
    assert job.form_fields == ["First Name", "Email"]
    assert job.requires_resume is True


def test_inspected_jobs_holds_list():
    from worker.models.inspected_job import InspectedJob, InspectedJobs
    jobs = InspectedJobs(jobs=[
        InspectedJob(url="https://a.com", company="A", job_title="D",
                     form_fields=["Email"], requires_resume=False),
    ])
    assert len(jobs.jobs) == 1


def test_application_packet_json_instructions_is_string():
    from worker.models.application_packet import ApplicationPacket
    import json
    instructions = json.dumps({"First Name": "Tanner", "Email": "t@example.com"})
    packet = ApplicationPacket(
        url="https://example.com",
        company="Acme",
        job_title="Engineer",
        json_instructions=instructions,
        requires_resume=False,
    )
    assert isinstance(packet.json_instructions, str)
    parsed = json.loads(packet.json_instructions)
    assert parsed["First Name"] == "Tanner"


def test_application_packets_holds_list():
    from worker.models.application_packet import ApplicationPacket, ApplicationPackets
    import json
    packets = ApplicationPackets(packets=[
        ApplicationPacket(
            url="https://a.com", company="A", job_title="D",
            json_instructions=json.dumps({"Email": "a@b.com"}),
            requires_resume=False,
        )
    ])
    assert len(packets.packets) == 1
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
uv run pytest worker/tests/models/test_crew_models.py -v
```

Expected: `ModuleNotFoundError` for `worker.models.job_listing`

- [ ] **Step 3: Create `worker/models/job_listing.py`**

```python
from pydantic import BaseModel


class JobListing(BaseModel):
    """A single job listing returned by the Searcher agent."""

    url: str
    company: str
    job_title: str


class SearchResults(BaseModel):
    """All job listings found by the Searcher agent."""

    jobs: list[JobListing]
```

- [ ] **Step 4: Create `worker/models/inspected_job.py`**

```python
from pydantic import BaseModel


class InspectedJob(BaseModel):
    """A job listing enriched with form fields extracted from its application page."""

    url: str
    company: str
    job_title: str
    form_fields: list[str]   # exact labels extracted from the rendered DOM
    requires_resume: bool    # True if <input type="file"> was found on the page


class InspectedJobs(BaseModel):
    """All inspected jobs produced by the Field Inspector agent."""

    jobs: list[InspectedJob]
```

- [ ] **Step 5: Create `worker/models/application_packet.py`**

```python
from pydantic import BaseModel


class ApplicationPacket(BaseModel):
    """Instructions for the Browser agent to fill and submit one job application."""

    url: str
    company: str
    job_title: str
    json_instructions: str   # JSON-encoded string: '{"First Name": "Tanner", ...}'
    requires_resume: bool


class ApplicationPackets(BaseModel):
    """All application packets produced by the Evaluator agent."""

    packets: list[ApplicationPacket]
```

- [ ] **Step 6: Run tests — verify they PASS**

```bash
uv run pytest worker/tests/models/test_crew_models.py -v
```

Expected: 7 tests pass

- [ ] **Step 7: Commit**

```bash
git add worker/models/job_listing.py worker/models/inspected_job.py \
        worker/models/application_packet.py \
        worker/tests/__init__.py worker/tests/models/__init__.py \
        worker/tests/models/test_crew_models.py
git commit -m "feat: add Pydantic models for structured crew pipeline output"
```

---

## Task 2: Field Inspector Tool

**Files:**
- Create: `worker/tools/field_inspector_tool.py`
- Create: `worker/tests/tools/__init__.py`
- Create: `worker/tests/tools/test_field_inspector_tool.py`

- [ ] **Step 1: Write the failing tests**

Create `worker/tests/tools/__init__.py` (empty), then create `worker/tests/tools/test_field_inspector_tool.py`:

```python
import json
from unittest.mock import MagicMock, patch


def _make_page(labels=None, inputs=None, textareas=None, selects=None, file_inputs=0):
    """Build a minimal mock Playwright Page object."""
    page = MagicMock()

    def mock_locator(selector):
        loc = MagicMock()
        if "label" in selector and "input" not in selector and "textarea" not in selector and "select" not in selector:
            items = [_mock_element(text=t) for t in (labels or [])]
            loc.all.return_value = items
        elif "input[type=file]" in selector:
            loc.count.return_value = file_inputs
        elif selector.startswith("input"):
            items = [_mock_element(attrs=a) for a in (inputs or [])]
            loc.all.return_value = items
        elif selector.startswith("textarea"):
            items = [_mock_element(attrs=a) for a in (textareas or [])]
            loc.all.return_value = items
        elif selector.startswith("select"):
            items = [_mock_element(attrs=a) for a in (selects or [])]
            loc.all.return_value = items
        else:
            loc.all.return_value = []
            loc.count.return_value = 0
        return loc

    page.locator.side_effect = mock_locator
    return page


def _mock_element(text=None, attrs=None):
    el = MagicMock()
    el.inner_text.return_value = text or ""
    attrs = attrs or {}
    el.get_attribute.side_effect = lambda a: attrs.get(a, "")
    return el


def test_extracts_label_text():
    from worker.tools.field_inspector_tool import _extract_fields
    page = _make_page(labels=["First Name", "Email Address"])
    fields = _extract_fields(page)
    assert "First Name" in fields
    assert "Email Address" in fields


def test_strips_trailing_colon_and_asterisk():
    from worker.tools.field_inspector_tool import _extract_fields
    page = _make_page(labels=["First Name*", "Email:"])
    fields = _extract_fields(page)
    assert "First Name" in fields
    assert "Email" in fields


def test_deduplicates_fields():
    from worker.tools.field_inspector_tool import _extract_fields
    page = _make_page(labels=["Email", "Email"])
    fields = _extract_fields(page)
    assert fields.count("Email") == 1


def test_extracts_input_placeholder():
    from worker.tools.field_inspector_tool import _extract_fields
    page = _make_page(inputs=[{"placeholder": "Your phone number"}])
    fields = _extract_fields(page)
    assert "Your phone number" in fields


def test_skips_empty_labels():
    from worker.tools.field_inspector_tool import _extract_fields
    page = _make_page(labels=["", "  ", "Valid Field"])
    fields = _extract_fields(page)
    assert "" not in fields
    assert "  " not in fields
    assert "Valid Field" in fields


def test_tool_returns_json_with_form_fields():
    from worker.tools.field_inspector_tool import field_inspector_tool

    mock_page = _make_page(labels=["First Name", "Email"], file_inputs=1)

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert "First Name" in data["form_fields"]
    assert "Email" in data["form_fields"]
    assert data["requires_resume"] is True
    assert data["url"] == "https://example.com"


def test_tool_returns_empty_on_playwright_error():
    from worker.tools.field_inspector_tool import field_inspector_tool

    with patch("worker.tools.field_inspector_tool.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.side_effect = Exception("browser crashed")
        result = field_inspector_tool.run("https://example.com")

    data = json.loads(result)
    assert data["form_fields"] == []
    assert data["requires_resume"] is False
    assert "error" in data
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
uv run pytest worker/tests/tools/test_field_inspector_tool.py -v
```

Expected: `ModuleNotFoundError` for `worker.tools.field_inspector_tool`

- [ ] **Step 3: Create `worker/tools/field_inspector_tool.py`**

```python
import json

from crewai.tools import tool
from playwright.sync_api import Page, sync_playwright

from worker.logging_config import get_logger

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


@tool("Field Inspector")
def field_inspector_tool(url: str) -> str:
    """Visit a job application URL and extract the names of all visible form fields.

    Returns a JSON string with keys: url, form_fields (list of label strings),
    requires_resume (bool). On any error returns empty form_fields with an error key.
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

            fields = _extract_fields(page)
            requires_resume = page.locator("input[type=file]").count() > 0
            browser.close()

        result = {"url": url, "form_fields": fields, "requires_resume": requires_resume}
        logger.info("fields_extracted", url=url, field_count=len(fields))
        return json.dumps(result)

    except Exception as exc:
        logger.error("field_inspection_failed", url=url, error=str(exc))
        return json.dumps({
            "url": url,
            "form_fields": [],
            "requires_resume": False,
            "error": str(exc),
        })
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
uv run pytest worker/tests/tools/test_field_inspector_tool.py -v
```

Expected: 7 tests pass

- [ ] **Step 5: Manual smoke test against a real Greenhouse URL**

```bash
uv run python -c "
from worker.tools.field_inspector_tool import field_inspector_tool
import json
result = field_inspector_tool.run('https://boards.greenhouse.io/hackerrank/jobs/5802144')
data = json.loads(result)
print('Fields found:', data['form_fields'])
print('Requires resume:', data['requires_resume'])
"
```

Expected: `form_fields` list with entries like `["First Name", "Last Name", "Email", ...]`, not empty.

- [ ] **Step 6: Commit**

```bash
git add worker/tools/field_inspector_tool.py \
        worker/tests/tools/__init__.py \
        worker/tests/tools/test_field_inspector_tool.py
git commit -m "feat: add field_inspector_tool to extract form fields via Playwright"
```

---

## Task 3: Field Inspector Agent

**Files:**
- Create: `worker/agents/field_inspector.py`

- [ ] **Step 1: Write the failing test**

Add to `worker/tests/models/test_crew_models.py` (append at the bottom):

```python
def test_build_field_inspector_returns_agent():
    from unittest.mock import patch
    # Patch LLM to avoid needing Ollama running during tests
    with patch("worker.agents.field_inspector.LLM"):
        from worker.agents.field_inspector import build_field_inspector
        agent = build_field_inspector()
    assert agent.role == "Form Field Inspector"
    assert agent.max_iter == 8
    assert agent.allow_delegation is False
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
uv run pytest worker/tests/models/test_crew_models.py::test_build_field_inspector_returns_agent -v
```

Expected: `ModuleNotFoundError` for `worker.agents.field_inspector`

- [ ] **Step 3: Create `worker/agents/field_inspector.py`**

```python
from crewai import Agent, LLM

from worker.config import settings
from worker.tools.field_inspector_tool import field_inspector_tool


def build_field_inspector() -> Agent:
    """Build the Form Field Inspector agent.

    Visits each job URL and extracts the exact form field labels from the
    rendered DOM. Uses the fast model since no reasoning is required —
    just sequential tool calls.
    """
    llm = LLM(model=settings.fast_model, base_url=settings.ollama_base_url)
    return Agent(
        role="Form Field Inspector",
        goal="Visit each job URL and return the exact form fields present on the page.",
        backstory=(
            "You are a precise DOM inspector. For each job URL you receive, you call the "
            "Field Inspector tool exactly once and report what fields you found. "
            "You never skip a URL and never call the tool more than once per URL."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[field_inspector_tool],
        llm=llm,
        max_iter=8,
    )
```

- [ ] **Step 4: Run test — verify it PASSES**

```bash
uv run pytest worker/tests/models/test_crew_models.py::test_build_field_inspector_returns_agent -v
```

Expected: 1 test passes

- [ ] **Step 5: Commit**

```bash
git add worker/agents/field_inspector.py \
        worker/tests/models/test_crew_models.py
git commit -m "feat: add FieldInspector agent"
```

---

## Task 4: Wire the 4-Stage Pipeline in crew.py

**Files:**
- Modify: `worker/crew.py`

- [ ] **Step 1: Write the failing test**

Create `worker/tests/test_crew.py`:

```python
import json
from unittest.mock import MagicMock, patch


def test_run_crew_injects_personal_data_into_inputs(tmp_path):
    """personal_data.json contents must appear in the crew inputs dict."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_data = {"First Name": "Tanner", "Email": "t@example.com"}
    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text(json.dumps(personal_data))

    captured_inputs = {}

    def fake_kickoff(inputs):
        captured_inputs.update(inputs)
        return MagicMock(__str__=lambda self: "done")

    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = fake_kickoff

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Crew", return_value=mock_crew_instance),
        patch.object(crew_module, "set_current_task_id"),
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer", location="Remote",
            min_salary=100000, job_keywords=["Python"],
            company="", job_website="",
        )
        crew_module.run_crew(criteria, task_id="test-123")

    assert "personal_data" in captured_inputs
    loaded = json.loads(captured_inputs["personal_data"])
    assert loaded["First Name"] == "Tanner"


def test_crew_has_four_tasks(tmp_path):
    """Crew must be built with exactly 4 tasks."""
    import worker.crew as crew_module
    from worker.models.search_criteria import SearchCriteria

    personal_data = {"First Name": "Tanner"}
    personal_file = tmp_path / "personal_data.json"
    personal_file.write_text(json.dumps(personal_data))

    tasks_passed = []

    def capture_crew(**kwargs):
        tasks_passed.extend(kwargs.get("tasks", []))
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(__str__=lambda self: "done")
        return crew

    with (
        patch.object(crew_module, "settings") as mock_settings,
        patch.object(crew_module, "build_searcher", return_value=MagicMock()),
        patch.object(crew_module, "build_field_inspector", return_value=MagicMock()),
        patch.object(crew_module, "build_evaluator", return_value=MagicMock()),
        patch.object(crew_module, "build_browser", return_value=MagicMock()),
        patch.object(crew_module, "Crew", side_effect=capture_crew),
        patch.object(crew_module, "set_current_task_id"),
    ):
        mock_settings.personal_data_path = personal_file
        criteria = SearchCriteria(
            job_title="Engineer", location="Remote",
            min_salary=100000, job_keywords=["Python"],
            company="", job_website="",
        )
        crew_module.run_crew(criteria)

    assert len(tasks_passed) == 4
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
uv run pytest worker/tests/test_crew.py -v
```

Expected: `ImportError` or assertion failure — `build_field_inspector` doesn't exist in crew.py yet

- [ ] **Step 3: Rewrite `worker/crew.py`**

```python
import json

from crewai import Crew, Process, Task

from worker.agents.browser import build_browser
from worker.agents.evaluator import build_evaluator
from worker.agents.field_inspector import build_field_inspector
from worker.agents.searcher import build_searcher
from worker.config import settings
from worker.logging_config import get_logger
from worker.models.application_packet import ApplicationPackets
from worker.models.inspected_job import InspectedJobs
from worker.models.job_listing import SearchResults
from worker.models.search_criteria import SearchCriteria
from worker.tools.browser_tool import set_current_task_id

logger = get_logger(__name__)

_TASK_SEARCH_DESCRIPTION = (
    "Search for open positions using the following mandatory criteria:\n"
    "- Job Title: {job_title}\n"
    "- Location: {location}\n"
    "- Keywords required in description: {job_keywords}\n"
    "- Minimum Salary: ${min_salary}\n\n"
    "OPTIONAL CONSTRAINTS:\n"
    "- Target Company (if provided, only search this company): {company}\n"
    "- Target Website (if provided, use site: operator): {job_website}\n\n"
    "You MUST search specifically on job boards. Run at least 3 of these queries:\n"
    '  "{job_title} {location} site:indeed.com"\n'
    '  "{job_title} {location} site:greenhouse.io"\n'
    '  "{job_title} {location} site:lever.co"\n'
    "Only keep results whose URL contains one of these patterns:\n"
    "  indeed.com/viewjob, greenhouse.io/jobs/,\n"
    "  lever.co/jobs/, boards.greenhouse.io/, jobs.lever.co/, workday.com/jobs/\n\n"
    "DISCARD any result that looks like a social post, article, hashtag feed, or profile page.\n\n"
    "Find up to 5 highly relevant job listings. For each listing output:\n"
    "- url: the direct application URL\n"
    "- company: the company name\n"
    "- job_title: the exact job title"
)

_TASK_INSPECT_DESCRIPTION = (
    "You have a list of job listings from the Searcher. "
    "For EACH job in the list, call the Field Inspector tool exactly once with its URL.\n"
    "Do NOT skip any job. Do NOT call the tool more than once per URL.\n"
    "Collect all results and output them as an InspectedJobs object with the form_fields "
    "and requires_resume value returned by the tool for each job."
)

_TASK_EVALUATE_DESCRIPTION = (
    "You have a list of inspected jobs from the Field Inspector. "
    "Each job has a list of exact form_fields extracted from its application page.\n\n"
    "Personal data to use when filling fields:\n"
    "{personal_data}\n\n"
    "Steps:\n"
    "1. Discard any jobs that do not meet the ${min_salary} salary requirement "
    "or lack the keywords: {job_keywords}.\n"
    "2. For each approved job, create an ApplicationPacket:\n"
    "   - url: exact URL from the inspector (do not change it)\n"
    "   - company: company name\n"
    "   - job_title: job title\n"
    "   - json_instructions: a JSON-encoded STRING mapping each form_field that matches "
    "personal data to its value. Use ONLY field names from the form_fields list — "
    "do NOT invent field names. "
    'Example: \'{{"First Name": "Tanner", "Email": "tanner@example.com"}}\'\n'
    "   - requires_resume: the requires_resume boolean from the inspector\n"
    "3. Output one ApplicationPacket per approved job. Do not skip any approved job."
)

_TASK_APPLY_DESCRIPTION = (
    "You have a list of ApplicationPackets from the Evaluator. "
    "For EACH packet, immediately call the Browser Form Fitter tool with:\n"
    "- url: the exact URL from the packet\n"
    "- json_instructions: the exact json_instructions string from the packet\n"
    "- requires_resume: the boolean value from the packet\n"
    "Do NOT search the web. Do NOT skip any packets. Call Browser Form Fitter once per job."
)


def run_crew(criteria: SearchCriteria, task_id: str | None = None) -> str:
    """Build a fresh 4-stage crew and run it for the given search criteria.

    A new crew is built per run to prevent context bleed between tasks.
    Stages: Searcher → Field Inspector → Evaluator → Browser.
    """
    searcher = build_searcher()
    field_inspector = build_field_inspector()
    evaluator = build_evaluator()
    browser_agent = build_browser()

    task_search = Task(
        description=_TASK_SEARCH_DESCRIPTION,
        expected_output="SearchResults JSON with jobs list containing url, company, job_title.",
        agent=searcher,
        output_pydantic=SearchResults,
    )
    task_inspect = Task(
        description=_TASK_INSPECT_DESCRIPTION,
        expected_output="InspectedJobs JSON with form_fields and requires_resume per job.",
        agent=field_inspector,
        output_pydantic=InspectedJobs,
    )
    task_evaluate = Task(
        description=_TASK_EVALUATE_DESCRIPTION,
        expected_output="ApplicationPackets JSON with json_instructions and requires_resume per approved job.",
        agent=evaluator,
        output_pydantic=ApplicationPackets,
    )
    task_apply = Task(
        description=_TASK_APPLY_DESCRIPTION,
        expected_output="Final report of all submitted applications.",
        agent=browser_agent,
    )

    crew = Crew(
        agents=[searcher, field_inspector, evaluator, browser_agent],
        tasks=[task_search, task_inspect, task_evaluate, task_apply],
        process=Process.sequential,
        verbose=True,
    )

    personal_data = json.loads(settings.personal_data_path.read_text())

    inputs = {
        "job_title": criteria.job_title,
        "location": criteria.location,
        "min_salary": criteria.min_salary,
        "job_keywords": ", ".join(criteria.job_keywords),
        "company": criteria.company or "",
        "job_website": criteria.job_website or "",
        "personal_data": json.dumps(personal_data),
    }

    set_current_task_id(task_id)
    logger.info("crew_kickoff", task_id=task_id, job_title=criteria.job_title)
    try:
        result = crew.kickoff(inputs=inputs)
    finally:
        set_current_task_id(None)
    logger.info("crew_complete", task_id=task_id)
    return str(result)
```

- [ ] **Step 4: Run all tests — verify they PASS**

```bash
uv run pytest worker/tests/ -v
```

Expected: all tests pass (models + tool + agent + crew tests)

- [ ] **Step 5: Import smoke test**

```bash
uv run python -c "
from worker.crew import run_crew
from worker.tools.field_inspector_tool import field_inspector_tool
from worker.agents.field_inspector import build_field_inspector
from worker.models.job_listing import SearchResults
from worker.models.inspected_job import InspectedJobs
from worker.models.application_packet import ApplicationPackets
print('All imports: ok')
"
```

Expected: `All imports: ok`

- [ ] **Step 6: Commit**

```bash
git add worker/crew.py worker/tests/test_crew.py
git commit -m "feat: wire 4-stage pipeline with Field Inspector and structured Pydantic output"
```

---

## Final Verification

- [ ] **Full import check**

```bash
uv run python -c "from worker.crew import run_crew; print('ok')"
```

- [ ] **Field inspector tool smoke test against live URL**

```bash
uv run python -c "
import json
from worker.tools.field_inspector_tool import field_inspector_tool
result = field_inspector_tool.run('https://boards.greenhouse.io/hackerrank/jobs/5802144')
data = json.loads(result)
print('form_fields:', data['form_fields'])
print('requires_resume:', data['requires_resume'])
assert len(data['form_fields']) > 0, 'Expected fields — got empty list'
print('PASS')
"
```

- [ ] **Run full test suite**

```bash
uv run pytest worker/tests/ -v
```

Expected: all tests green

- [ ] **End-to-end: restart worker and insert test task**

```bash
# Terminal 1 (if not already running)
ollama serve

# Terminal 2
uv run python -m worker.main
```

```sql
-- Supabase SQL Editor
UPDATE search_tasks SET status = 'done' WHERE status IN ('pending', 'running');
INSERT INTO search_tasks (job_title, location, min_salary, keywords, status)
VALUES ('AI Engineer', 'Remote', 120000, ARRAY['Python', 'FastAPI'], 'pending');
```

Watch for:
1. Searcher produces `SearchResults` JSON
2. Field Inspector calls `field_inspector_tool` once per URL, produces `InspectedJobs`
3. Evaluator maps fields to personal data, produces `ApplicationPackets` with non-empty `json_instructions`
4. Browser calls `Browser Form Fitter` once per packet
5. `applications` table has rows
