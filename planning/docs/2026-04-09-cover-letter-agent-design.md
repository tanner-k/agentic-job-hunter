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

The Cover Letter Writer is a no-op for packets where `requires_cover_letter=False` — it passes them through unchanged.

---

## Data Model Changes

### `InspectedJob`

Add field:

```python
requires_cover_letter: bool
```

The Field Inspector's prompt is updated to detect cover letter fields (text areas or file uploads labeled "cover letter") the same way it already detects resume upload fields.

### `ApplicationPacket`

Add two optional fields:

```python
cover_letter_text: str | None = None   # pasted into text fields by the Browser
cover_letter_path: str | None = None   # absolute path to PDF, used for file uploads
```

---

## New Files

| Path | Purpose |
|------|---------|
| `src/worker/agents/cover_letter_writer.py` | Agent definition |
| `src/worker/tools/cover_letter_renderer.py` | PDF renderer tool + context loader tool |
| `worker/personal/cover_letter_context.md` | User-maintained background context (not committed) |
| `worker/personal/cover_letters/` | Output directory for rendered PDFs |

---

## Agent

**File:** `src/worker/agents/cover_letter_writer.py`

- **Role:** Cover Letter Writer
- **Goal:** Draft a tailored, compelling cover letter for each job application that requires one.
- **Model:** `settings.reasoning_model` (same as Evaluator)
- **Tools:**
  - `resume_loader_tool` (existing)
  - `cover_letter_context_loader_tool` (new) — reads `cover_letter_context.md`
  - `pdf_renderer_tool` (new) — renders the letter to PDF, returns the path

**Task inputs** (passed via crew template variables): `job_title`, `company`, `job_description`, `application_packets` (JSON).

**Agent steps:**
1. Call `resume_loader_tool` and `cover_letter_context_loader_tool` to gather context
2. Draft a cover letter tailored to the job title, company, and job description
3. Call `pdf_renderer_tool` to render and save the PDF
4. Output updated `ApplicationPackets` with `cover_letter_text` and `cover_letter_path` populated for packets where `requires_cover_letter=True`

---

## Tools

### `cover_letter_context_loader_tool`

Reads `settings.cover_letter_context_path` (a `.md` file). If the file does not exist, logs a warning and returns an empty string — the agent proceeds with resume context only.

### `pdf_renderer_tool`

**Signature:**
```python
pdf_renderer_tool(company: str, job_title: str, cover_letter_text: str) -> str
```

- Sanitizes `company` and `job_title` for filename use (strips special chars, replaces spaces with underscores)
- Creates `settings.cover_letter_output_dir` if it does not exist
- Renders the letter as plain body text (Helvetica 11pt, standard margins, auto line-wrap) using `reportlab`
- Overwrites any existing file with the same name (idempotent per run)
- Returns absolute path to the PDF on success, or an error string on failure

---

## Settings Changes

```python
cover_letter_context_path: Path = Path("./worker/personal/cover_letter_context.md")
cover_letter_output_dir: Path = Path("./worker/personal/cover_letters")
```

---

## Error Handling

| Failure | Behavior |
|---------|---------|
| `cover_letter_context.md` missing | Log warning, proceed with resume context only |
| PDF rendering fails | Log error, leave `cover_letter_path=None`; Browser skips file upload |
| Agent fails entirely | Pass `ApplicationPackets` through unchanged; Browser applies without cover letter |

No failure mode crashes the run. Cover letter generation is additive — its absence degrades gracefully.

---

## Testing

| Test | Type |
|------|------|
| `cover_letter_context_loader_tool` — missing file, empty file, valid file | Unit |
| `pdf_renderer_tool` — filename sanitization, directory creation, overwrite behavior | Unit |
| `build_cover_letter_writer()` — agent builds without error | Unit |
| Agent populates `cover_letter_text` and `cover_letter_path` for `requires_cover_letter=True` packets | Integration (tools mocked) |
| Agent passes through packets with `requires_cover_letter=False` unchanged | Integration (tools mocked) |

---

## Dependencies

- `reportlab` — add via `uv add reportlab`
- `pdfplumber` — already present (used by `resume_loader_tool`)
