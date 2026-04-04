# Field Inspector Agent — Design Spec

**Date:** 2026-04-03
**Status:** Approved

---

## Problem

The Evaluator agent currently guesses form field names (e.g. "First Name", "Email") without visiting
the job page. These guesses rarely match the actual labels on the form, so the Browser fills nothing
and the `applications` table stays empty.

---

## Solution

Add a **Field Inspector** agent between the Searcher and Evaluator. It visits each job URL with
Playwright, extracts the actual form field labels from the rendered DOM, and passes a structured
list to the Evaluator. The Evaluator then maps exact field names to real personal data values —
no more guessing.

---

## Pipeline (4 stages)

```
Searcher ──► Field Inspector ──► Evaluator ──► Browser
```

Each stage produces a typed Pydantic object consumed by the next task via CrewAI's
`output_pydantic` task parameter.

| Stage | Output type | Key fields |
|---|---|---|
| Searcher | `SearchResults` | `jobs: list[JobListing]` |
| Field Inspector | `InspectedJobs` | `jobs: list[InspectedJob]` |
| Evaluator | `ApplicationPackets` | `packets: list[ApplicationPacket]` |
| Browser | `str` | plain submission report |

---

## Pydantic Models

### `worker/models/job_listing.py` (new)
```python
class JobListing(BaseModel):
    url: str
    company: str
    job_title: str

class SearchResults(BaseModel):
    jobs: list[JobListing]
```

### `worker/models/inspected_job.py` (new)
```python
class InspectedJob(BaseModel):
    url: str
    company: str
    job_title: str
    form_fields: list[str]   # exact labels extracted from the rendered page
    requires_resume: bool    # True if <input type="file"> is present

class InspectedJobs(BaseModel):
    jobs: list[InspectedJob]
```

### `worker/models/application_packet.py` (new)
```python
class ApplicationPacket(BaseModel):
    url: str
    company: str
    job_title: str
    json_instructions: str   # JSON-encoded string: '{"First Name": "Tanner", "Email": "..."}'
    requires_resume: bool    # kept as str so browser_tool receives it without conversion

class ApplicationPackets(BaseModel):
    packets: list[ApplicationPacket]
```

---

## Field Inspector Tool

**File:** `worker/tools/field_inspector_tool.py` (new)

Uses Playwright headless Chromium (same config as `browser_tool.py`) to visit a URL and extract
form fields from the rendered DOM.

**Extraction strategy (priority order):**
1. `<label>` element inner text — most reliable on Greenhouse / Lever
2. `input[placeholder]`, `input[aria-label]` — catches unlabelled inputs
3. `textarea[placeholder]`, `textarea[aria-label]` — multi-line fields
4. `select[aria-label]`, `select[name]` — dropdown fields

**Exclusions:** `input[type=hidden]`, `input[type=submit]`, `input[type=button]`, `input[type=file]`

**File upload detection:** `input[type=file]` presence → `requires_resume=True`

**Return format (JSON string):**
```json
{
  "url": "https://boards.greenhouse.io/...",
  "form_fields": ["First Name", "Last Name", "Email", "Phone", "Resume"],
  "requires_resume": true
}
```

**Error handling:** Any exception returns `{form_fields: [], requires_resume: false, error: "..."}`
so the pipeline never breaks on a bad URL.

**Page load:** `networkidle` with 30s timeout, falls back to `domcontentloaded` on timeout.

---

## Field Inspector Agent

**File:** `worker/agents/field_inspector.py` (new)

```python
Agent(
    role="Form Field Inspector",
    goal="Visit each job URL and return the exact form fields present on the page.",
    backstory="You are a precise DOM inspector. For each job URL provided, you call the
               Field Inspector tool exactly once and report what you find.",
    tools=[field_inspector_tool],
    llm=fast_model,        # qwen3.5:9b — no reasoning needed, just tool calls
    max_iter=8,            # up to 5 jobs × 1 call + retries
    allow_delegation=False,
)
```

**Task description:** Instructs the agent to call `field_inspector_tool` once per URL from the
Searcher output. Do NOT skip any URL.

**Task output:** `output_pydantic=InspectedJobs`

---

## Updated `crew.py`

### Changes to existing tasks

**Searcher task:**
- Add `output_pydantic=SearchResults`
- `expected_output` updated to match schema

**Evaluator task:**
- Receives `InspectedJobs` as context (automatically via sequential process)
- Task description updated: use `form_fields` from the inspector — do NOT invent field names
- Personal data injected via `{personal_data}` template variable
- Add `output_pydantic=ApplicationPackets`

**Browser task:** unchanged (still reads `json_instructions` from packets)

### New task (between Searcher and Evaluator)

```python
task_inspect = Task(
    description=_TASK_INSPECT_DESCRIPTION,
    expected_output="InspectedJobs with form_fields and requires_resume for each URL.",
    agent=field_inspector,
    output_pydantic=InspectedJobs,
)
```

### `run_crew()` additions

```python
import json
personal_data = json.loads(settings.personal_data_path.read_text())
inputs = {
    ...existing...,
    "personal_data": json.dumps(personal_data),
}
```

### Agent / task order

```python
crew = Crew(
    agents=[searcher, field_inspector, evaluator, browser_agent],
    tasks=[task_search, task_inspect, task_evaluate, task_apply],
    process=Process.sequential,
)
```

---

## Files Changed

| File | Action |
|---|---|
| `worker/models/job_listing.py` | **Create** |
| `worker/models/inspected_job.py` | **Create** |
| `worker/models/application_packet.py` | **Create** |
| `worker/tools/field_inspector_tool.py` | **Create** |
| `worker/agents/field_inspector.py` | **Create** |
| `worker/crew.py` | **Modify** — 4 tasks, inject personal_data, output_pydantic on 3 tasks |

---

## Verification

1. `uv run python -c "from worker.tools.field_inspector_tool import field_inspector_tool; print('ok')"` — import check
2. `uv run python -c "from worker.crew import run_crew; print('ok')"` — crew import check
3. Manual tool test: `field_inspector_tool.run('https://boards.greenhouse.io/hackerrank/jobs/5802144')` — should return JSON with `form_fields` populated
4. Full crew run: insert a `pending` search task → confirm `InspectedJob` fields appear in logs → confirm `ApplicationPackets` has non-empty `json_instructions` → confirm `applications` table has rows
