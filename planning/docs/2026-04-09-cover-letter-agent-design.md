# Cover Letter Writer Agent — Design

**Date:** 2026-04-09
**Status:** Approved

## Overview

A new `CoverLetterWriter` CrewAI agent that generates tailored cover letters for job applications that require one. It sits between the Evaluator and Browser in the sequential pipeline and produces both a plain-text string (for text fields) and a rendered PDF (for file upload fields).

---

## Pipeline

```
Searcher → Field Inspector → Evaluator → Cover Letter Writer → Browser
```

The Cover Letter Writer is a no-op for packets where `requires_cover_letter=False` — it passes them through with `cover_letter_text=None` and `cover_letter_path=None`.

In `dry_run` mode, the Cover Letter Writer is **excluded** from the crew (same as the Browser). The dry run return value remains `task_evaluate.output.pydantic`. Since Browser is also excluded in dry run, the `context=[task_inspect]` on `task_cover_letter` does not affect this path.

---

## Data Model Changes

### `InspectedJob` (existing: `src/worker/models/inspected_job.py`)

Add two **required** fields (no defaults — the tool always returns them):

```python
requires_cover_letter: bool
job_description: str  # visible page text, trimmed to 4000 chars
```

These are populated by `field_inspector_tool` via Playwright DOM inspection.

`InspectedJobs` (wrapper model) requires no structural changes.

### `ApplicationPacket` (existing: `src/worker/models/application_packet.py`)

Add two optional fields:

```python
cover_letter_text: str | None = None
cover_letter_path: str | None = None
```

For pass-through packets (`requires_cover_letter=False`), both fields remain `None`. The Browser ignores null fields.

`ApplicationPackets` (existing: `job_applications: list[ApplicationPacket]`) requires no structural changes.

`job_description` is **not** added to `ApplicationPacket`. The Cover Letter Writer reads it from `InspectedJobs` via `context=[task_inspect]`.

---

## Field Inspector Tool Changes

**File:** `src/worker/tools/field_inspector_tool.py`

### 1. New helper: `_get_input_label`

Add as a module-level private function:

```python
from playwright.sync_api import Locator, Page

def _get_input_label(page: Page, element: Locator) -> str:
```

Returns the best available label text for a `Locator` by checking (in order):
1. `<label for="<element_id>">` — retrieve element's `id` attribute, then `page.locator(f'label[for="{id}"]').inner_text()`
2. Wrapping `<label>` ancestor — `element.locator("xpath=ancestor::label[1]").inner_text()`
3. `aria-label` attribute — `element.get_attribute("aria-label")`
4. `name` attribute — `element.get_attribute("name")`

Returns empty string if none found. Each step is wrapped in `contextlib.suppress(Exception)`.

This helper is specifically for cover letter detection. `_extract_fields` (for `form_fields`) continues to use its existing attr-only approach — the two are intentionally independent.

### 2. Extract `job_description` (inside `try` block alongside `_extract_fields`)

Inside `_inspector_work`, inside the `try` block that contains `_extract_fields`, immediately after `click_through_to_form(page)` and before `browser.close()`:

```python
raw_text = page.evaluate("document.body.innerText") or ""
job_description = raw_text[:4000]
```

Include `job_description` in the return JSON.

### 3. Replace `requires_resume` heuristic with label-aware classification (inside `try` block)

The current `page.locator("input[type=file]").count() > 0` grabs all file inputs including cover letter ones. Replace inside the same `try` block:

```python
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
```

The `result` dict is updated:

```python
result = {
    "url": url,
    "form_fields": fields,
    "requires_resume": requires_resume,
    "requires_cover_letter": requires_cover_letter,
    "job_description": job_description,
}
```

### 4. Update `_TASK_INSPECT_DESCRIPTION`

`_TASK_INSPECT_DESCRIPTION` in `crew.py` is updated to instruct the Field Inspector agent to include `requires_cover_letter` and `job_description` in its `InspectedJobs` output alongside the existing fields.

### 5. Update all error paths

All error-return JSON objects (in `_inspector_work` exception, `field_inspector_tool` timeout, `field_inspector_tool` executor error) are updated:

```python
{
    "url": ..., "form_fields": [],
    "requires_resume": False, "requires_cover_letter": False,
    "job_description": "", "error": ...
}
```

---

## New Files

| Path | Purpose |
|------|---------|
| `src/worker/agents/cover_letter_writer.py` | Agent definition |
| `src/worker/tools/cover_letter_context_loader.py` | Tool that reads `cover_letter_context.md` |
| `src/worker/tools/cover_letter_renderer.py` | Tool that renders cover letter text to PDF |
| `./worker/personal/cover_letter_context.md` | User-maintained background context (not committed) |
| `./worker/personal/cover_letters/` | Output directory for rendered PDFs |

All `./worker/personal/` paths are relative to the repo root — same prefix as `resume_path` and `personal_data_path`.

---

## Agent

**File:** `src/worker/agents/cover_letter_writer.py`

- **Role:** Cover Letter Writer
- **Goal:** Draft a tailored, compelling cover letter for each job application that requires one.
- **Model:** `settings.reasoning_model` (same as Evaluator)
- **Tools:** `resume_loader_tool`, `cover_letter_context_loader_tool`, `pdf_renderer_tool`

**Task input:** `ApplicationPackets` JSON arrives as the sequential output of `task_evaluate` (via CrewAI's `{previous_task_output}` mechanism). `InspectedJobs` JSON arrives separately via `context=[task_inspect]`. `_TASK_COVER_LETTER_DESCRIPTION` explicitly names both sources so the agent does not confuse them.

URL correlation: `ApplicationPacket.url` matches `InspectedJob.url`.

**Task definition:**

```python
task_cover_letter = Task(
    description=_TASK_COVER_LETTER_DESCRIPTION,
    expected_output=(
        "ApplicationPackets JSON identical to the input, with cover_letter_text and "
        "cover_letter_path populated for each packet that had requires_cover_letter=True. "
        "If PDF rendering failed, cover_letter_path must be null but cover_letter_text "
        "must still be set. Packets with requires_cover_letter=False are passed through "
        "with cover_letter_text=null and cover_letter_path=null."
    ),
    agent=cover_letter_writer,
    output_pydantic=ApplicationPackets,
    context=[task_inspect],
)
```

**`_TASK_COVER_LETTER_DESCRIPTION`** instructs the agent to:

1. Call `resume_loader_tool` and `cover_letter_context_loader_tool` **once** at the start. Reuse results for all packets.
2. The `ApplicationPackets` to process are in your sequential input (`{previous_task_output}`). The `InspectedJobs` data (containing `job_description`) is in your context from the Field Inspector task.
3. For each packet where `requires_cover_letter=True`:
   - Find the `InspectedJob` where `InspectedJob.url == ApplicationPacket.url`. If no match is found, log a warning and use empty `job_description` — do not halt.
   - Draft the cover letter text tailored to `job_title`, `company`, and `job_description`
   - Set `cover_letter_text` to the drafted string **before** calling `pdf_renderer_tool`
   - Call `pdf_renderer_tool(company, job_title, cover_letter_text)`
   - If result starts with `"Error:"`, set `cover_letter_path=null` and continue — do not halt
   - Otherwise set `cover_letter_path` to the returned path
4. For packets where `requires_cover_letter=False`, leave `cover_letter_text=null` and `cover_letter_path=null`
5. Output complete `ApplicationPackets` JSON including all packets

---

## Tools

### `cover_letter_context_loader_tool`

**File:** `src/worker/tools/cover_letter_context_loader.py`

Reads `settings.cover_letter_context_path` (default: `./worker/personal/cover_letter_context.md`; always present via settings default). If the file does not exist, logs a warning and returns an empty string. Same pattern as `resume_loader_tool`.

### `pdf_renderer_tool`

**File:** `src/worker/tools/cover_letter_renderer.py`

**Signature:** `pdf_renderer_tool(company: str, job_title: str, cover_letter_text: str) -> str`

- Sanitizes `company` and `job_title`: strips non-alphanumeric chars (except spaces), replaces spaces with underscores, lowercases. If the sanitized result is empty, falls back to `"unknown_company"` or `"unknown_role"`.
- Appends `YYYYMMDD_HHMMSS` timestamp suffix.
- Creates `settings.cover_letter_output_dir` if missing.
- Renders body text (Helvetica 11pt, standard margins, auto line-wrap) using `reportlab`.
- Calls `.resolve()` on the output path before returning, so the returned value is always an absolute path.
- Returns the absolute path string on success.
- Returns `"Error: ..."` on any failure (rendering error, filesystem error, permission error). Does not raise. Same convention as `resume_loader_tool`.

---

## Settings Changes

```python
cover_letter_context_path: Path = Path("./worker/personal/cover_letter_context.md")
cover_letter_output_dir: Path = Path("./worker/personal/cover_letters")
```

---

## Browser Tool Changes

**File:** `src/worker/tools/browser_tool.py`

### New parameters

`_browser_work` and `browser_tool` gain two new optional parameters:

```python
cover_letter_text: str | None = None
cover_letter_path: str | None = None
```

### Resume upload update (required)

The existing resume upload code:

```python
file_input = page.locator("input[type='file']")
if file_input.count() > 0:
    file_input.first.set_input_files(str(resume_path))
```

must be updated to skip file inputs labeled "cover letter". Replace with:

```python
for fi in page.locator("input[type='file']").all():
    label = _get_cover_letter_label(page, fi).lower()
    if "cover letter" not in label:
        fi.set_input_files(str(resume_path))
        break
```

`_get_cover_letter_label` is `_get_input_label` from `field_inspector_tool` — either import it or duplicate the four-step label lookup locally. The spec does not mandate sharing; either approach is acceptable.

### Cover letter fill logic (after standard field filling and resume upload)

1. Detect cover letter file upload: file inputs whose label contains "cover letter" (case-insensitive)
2. Detect cover letter text area: `<textarea>` elements whose label contains "cover letter" (case-insensitive)
3. If a cover letter file upload field is present and `cover_letter_path` is not `None`: upload the file using `set_input_files(cover_letter_path)`. Skip the text area even if present.
4. If a cover letter file upload field is present but `cover_letter_path` is `None`: skip the file upload, fall through to step 5.
5. If a cover letter text area is present and no file upload was completed: paste `cover_letter_text` if not `None`; otherwise log a warning and skip.
6. If no cover letter field is detected: skip silently.

`_TASK_APPLY_DESCRIPTION` in `crew.py` is updated to instruct the Browser to pass `cover_letter_text` and `cover_letter_path` from each `ApplicationPacket` to `browser_tool`.

---

## Error Handling

| Failure | Behavior |
|---------|---------|
| `cover_letter_context.md` missing | Log warning; proceed with resume context only |
| `pdf_renderer_tool` returns `"Error:"` | `cover_letter_path=null`; `cover_letter_text` still set; Browser falls back to text paste if available |
| `cover_letter_path=null` + form has only file upload | Browser logs warning and skips; application submitted without cover letter |
| No matching `InspectedJob` URL found | Agent logs warning; proceeds with empty `job_description` |
| Agent task produces malformed output (Pydantic coercion) | `cover_letter_*` fields default to `None`; Browser applies without cover letter |
| Agent task raises unhandled exception | Crew fails — same as any other unhandled crew failure |

---

## Testing

| Test | Type |
|------|------|
| `cover_letter_context_loader_tool` — missing file returns empty string | Unit |
| `cover_letter_context_loader_tool` — empty file returns empty string | Unit |
| `cover_letter_context_loader_tool` — valid file returns content | Unit |
| `pdf_renderer_tool` — filename sanitization (normal chars) | Unit |
| `pdf_renderer_tool` — empty post-sanitization falls back to `"unknown_company"` / `"unknown_role"` | Unit |
| `pdf_renderer_tool` — timestamp suffix appended | Unit |
| `pdf_renderer_tool` — output directory created if missing | Unit |
| `pdf_renderer_tool` — two calls with same company/title produce different filenames | Unit |
| `pdf_renderer_tool` — returns absolute path (`.resolve()` applied) | Unit |
| `pdf_renderer_tool` — returns `"Error:"` on rendering failure | Unit |
| `pdf_renderer_tool` — returns `"Error:"` on filesystem/permission error | Unit |
| `_get_input_label` — finds label via `<label for="id">` | Unit |
| `_get_input_label` — finds label via wrapping `<label>` | Unit |
| `_get_input_label` — finds label via `aria-label` attribute | Unit |
| `_get_input_label` — finds label via `name` attribute | Unit |
| `_get_input_label` — returns empty string when no label found | Unit |
| `field_inspector_tool` — `requires_cover_letter=True` for cover letter textarea | Unit |
| `field_inspector_tool` — `requires_cover_letter=True` for cover letter file input | Unit |
| `field_inspector_tool` — `requires_cover_letter=False` when no cover letter field | Unit |
| `field_inspector_tool` — `requires_resume=True` only for non-cover-letter file inputs | Unit |
| `field_inspector_tool` — page with both resume and cover letter file inputs sets both flags `True` | Unit |
| `field_inspector_tool` — `job_description` extracted and trimmed to 4000 chars | Unit |
| `field_inspector_tool` — error path includes `requires_cover_letter=False` and `job_description=""` | Unit |
| `build_cover_letter_writer()` — builds without error | Unit |
| Agent populates `cover_letter_text` and `cover_letter_path` for `requires_cover_letter=True` packets | Integration (tools mocked) |
| Agent passes through `requires_cover_letter=False` packets with both fields `None` | Integration (tools mocked) |
| Agent sets `cover_letter_path=null` when `pdf_renderer_tool` returns `"Error:"` | Integration (tools mocked) |
| Agent proceeds with empty `job_description` when no matching `InspectedJob` URL | Integration (tools mocked) |
| Browser uploads resume to non-cover-letter file input only | Unit (`_browser_work`) |
| Browser uploads cover letter file when `cover_letter_path` set and cover letter file input present | Unit (`_browser_work`) |
| Browser skips when `cover_letter_path=null` and form has only cover letter file upload | Unit (`_browser_work`) |
| Browser falls back to text paste when `cover_letter_path=null` but cover letter text area present | Unit (`_browser_work`) |
| Browser uses file upload (not text area) when both present and `cover_letter_path` set | Unit (`_browser_work`) |
| Cover Letter Writer excluded in `dry_run=True`; return value is `task_evaluate.output.pydantic` | Unit (`run_crew`) |

---

## Out of Scope

- `_record_application` in `browser_tool.py` is not updated to log cover letter submission status. Future improvement.
- Browser timeout (120s) is considered sufficient for `set_input_files` with a PDF. No change.

---

## Dependencies

- `reportlab` — add via `uv add reportlab`
- `pdfplumber` — already present
