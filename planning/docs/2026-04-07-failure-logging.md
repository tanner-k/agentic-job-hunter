# Failure Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured failure reporting to every agent output and log failures inline to Supabase — no dedicated tracking agent, just a lightweight logger called directly when a step fails.

**Architecture:** Every agent output model gains `failed: bool` and `failed_reason: str | None`. After each pipeline step, if the output signals failure, the pipeline calls `FailureLogger.log()` inline. The logger writes a `FailureRecord` (step name, reason, timestamp, job URL) to Supabase. No extra CrewAI agent or task is involved.

**Tech Stack:** Python 3.12, CrewAI, Pydantic v2 (frozen models), Supabase (Postgres), existing `uv` environment.

---

> **Future Work — Failure Analysis Skill**
>
> Once failure logs accumulate, we'll need a way to review them systematically and turn patterns into action. The plan is to create a Claude Code skill (`failure-analysis`) that:
> - Queries `failure_logs` grouped by step and reason
> - Surfaces the most common failure modes
> - Produces a structured report (e.g. "form_filler fails 40% of the time due to ATS modal blocking submission")
> - Outputs a prioritized list of plan suggestions for the next development cycle
>
> **Do not implement this skill yet.** Note it here so it's easy to spec when enough log data exists.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/backend/models/failure.py` | `FailureRecord` Pydantic model — canonical shape of a logged failure |
| Modify | `src/backend/models/*.py` (all agent output models) | Add `failed: bool` and `failed_reason: str \| None` fields |
| Create | `src/backend/logging/failure_logger.py` | `FailureLogger` — plain class that persists a `FailureRecord` to Supabase |
| Modify | `src/backend/crew.py` (or wherever the pipeline runs) | Call `FailureLogger.log()` inline after each step when `output.failed` |
| Create | `ops/migrations/001_add_failure_logs_table.sql` | Supabase migration adding the `failure_logs` table |
| Create | `tests/backend/test_failure_model.py` | Unit tests for `FailureRecord` validation |
| Create | `tests/backend/test_failure_logger.py` | Unit tests for `FailureLogger` (mock Supabase) |

---

## Task 1: Define the `FailureRecord` model

**Files:**
- Create: `src/backend/models/failure.py`
- Create: `tests/backend/test_failure_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/backend/test_failure_model.py
import pytest
from datetime import datetime, timezone
from src.backend.models.failure import FailureRecord


def test_failure_record_required_fields():
    record = FailureRecord(
        step="resume_parser",
        failed=True,
        failed_reason="LLM returned empty response after 3 retries",
        job_url="https://example.com/jobs/123",
        timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert record.step == "resume_parser"
    assert record.failed is True
    assert record.failed_reason == "LLM returned empty response after 3 retries"
    assert record.job_url == "https://example.com/jobs/123"


def test_failure_record_failed_reason_required_when_failed():
    with pytest.raises(ValueError, match="failed_reason must be set when failed=True"):
        FailureRecord(
            step="resume_parser",
            failed=True,
            failed_reason=None,
            job_url="https://example.com/jobs/123",
            timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc),
        )


def test_failure_record_reason_none_allowed_when_not_failed():
    record = FailureRecord(
        step="resume_parser",
        failed=False,
        failed_reason=None,
        job_url="https://example.com/jobs/123",
        timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert record.failed_reason is None


def test_failure_record_is_immutable():
    record = FailureRecord(
        step="resume_parser",
        failed=True,
        failed_reason="timeout",
        job_url="https://example.com/jobs/123",
        timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc),
    )
    with pytest.raises(Exception):
        record.step = "other_step"  # type: ignore
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/backend/test_failure_model.py -v
```

Expected: `ImportError` — `src/backend/models/failure.py` does not exist yet.

- [ ] **Step 3: Implement `FailureRecord`**

```python
# src/backend/models/failure.py
from datetime import datetime

from pydantic import BaseModel, model_validator


class FailureRecord(BaseModel, frozen=True):
    """Canonical shape of a single pipeline failure event."""

    step: str
    """Name of the pipeline step that failed (e.g. 'resume_parser', 'form_filler')."""

    failed: bool
    """True if this step failed."""

    failed_reason: str | None
    """Human-readable description of why the step failed. Required when failed=True."""

    job_url: str
    """URL of the job posting being processed when the failure occurred."""

    timestamp: datetime
    """UTC timestamp of when the failure was recorded."""

    @model_validator(mode="after")
    def validate_failed_reason(self) -> "FailureRecord":
        if self.failed and self.failed_reason is None:
            raise ValueError("failed_reason must be set when failed=True")
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/backend/test_failure_model.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backend/models/failure.py tests/backend/test_failure_model.py
git commit -m "feat: add FailureRecord Pydantic model with validation"
```

---

## Task 2: Add `failed` / `failed_reason` to all agent output models

**Files:**
- Modify: every `*Output` / `*Result` Pydantic model in `src/backend/models/`

> This task assumes agent output models already exist. If they do not, create stub output classes in the same files as their agents.

- [ ] **Step 1: List all existing agent output models**

```bash
grep -rn "class.*Output\|class.*Result" src/backend/models/ src/backend/agents/
```

Record each class name and file path — these are all the models to modify.

- [ ] **Step 2: For each output model, append the two new fields**

Add these fields after all domain-specific fields so existing call sites are unaffected:

```python
failed: bool = False
"""True if this agent step failed."""

failed_reason: str | None = None
"""Human-readable description of the failure. Must be set when failed=True."""
```

Example — if `ResumeParserOutput` exists:

```python
# src/backend/models/resume_parser.py  (before)
class ResumeParserOutput(BaseModel, frozen=True):
    name: str
    skills: list[str]

# src/backend/models/resume_parser.py  (after)
class ResumeParserOutput(BaseModel, frozen=True):
    name: str
    skills: list[str]
    failed: bool = False
    failed_reason: str | None = None
```

- [ ] **Step 3: Write tests confirming the new fields exist on each model**

Add to the existing test file for each model:

```python
# e.g. tests/backend/test_resume_parser_output.py
def test_resume_parser_output_has_failure_fields():
    out = ResumeParserOutput(name="Jane", skills=["Python"])
    assert out.failed is False
    assert out.failed_reason is None


def test_resume_parser_output_can_signal_failure():
    out = ResumeParserOutput(
        name="",
        skills=[],
        failed=True,
        failed_reason="LLM hallucinated empty response",
    )
    assert out.failed is True
    assert out.failed_reason == "LLM hallucinated empty response"
```

- [ ] **Step 4: Run the full test suite to catch regressions**

```bash
uv run pytest tests/ -v
```

Expected: all previously passing tests still pass; new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/backend/models/ tests/backend/
git commit -m "feat: add failed/failed_reason fields to all agent output models"
```

---

## Task 3: Create the Supabase `failure_logs` table

**Files:**
- Create: `ops/migrations/001_add_failure_logs_table.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- ops/migrations/001_add_failure_logs_table.sql
create table if not exists failure_logs (
    id            uuid        primary key default gen_random_uuid(),
    step          text        not null,
    failed_reason text        not null,
    job_url       text        not null,
    created_at    timestamptz not null default now()
);

-- Index for querying failures by step (most common dashboard filter)
create index if not exists idx_failure_logs_step on failure_logs (step);

-- Index for recent-failures queries
create index if not exists idx_failure_logs_created_at on failure_logs (created_at desc);
```

Note: only failed records are inserted, so `failed_reason` is `not null` — there is no need to store a `failed` boolean column.

- [ ] **Step 2: Apply the migration**

```bash
# Via Supabase CLI (if configured):
supabase db push

# Or paste the SQL directly in the Supabase dashboard → SQL Editor
```

Expected: `failure_logs` table appears in Supabase Table Editor with the four columns above.

- [ ] **Step 3: Commit**

```bash
git add ops/migrations/001_add_failure_logs_table.sql
git commit -m "chore: add failure_logs table migration"
```

---

## Task 4: Build `FailureLogger`

**Files:**
- Create: `src/backend/logging/failure_logger.py`
- Create: `tests/backend/test_failure_logger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/backend/test_failure_logger.py
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.backend.logging.failure_logger import FailureLogger
from src.backend.models.failure import FailureRecord


def _failed_record(step: str = "form_filler", reason: str = "selector not found") -> FailureRecord:
    return FailureRecord(
        step=step,
        failed=True,
        failed_reason=reason,
        job_url="https://example.com/jobs/42",
        timestamp=datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc),
    )


@patch("src.backend.logging.failure_logger.get_supabase_client")
def test_log_inserts_failure_record(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()

    logger = FailureLogger()
    record = _failed_record()
    logger.log(record)

    mock_client.table.assert_called_once_with("failure_logs")
    inserted = mock_client.table.return_value.insert.call_args[0][0]
    assert inserted["step"] == "form_filler"
    assert inserted["failed_reason"] == "selector not found"
    assert inserted["job_url"] == "https://example.com/jobs/42"


@patch("src.backend.logging.failure_logger.get_supabase_client")
def test_log_no_ops_when_not_failed(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    logger = FailureLogger()
    success_record = FailureRecord(
        step="form_filler",
        failed=False,
        failed_reason=None,
        job_url="https://example.com/jobs/42",
        timestamp=datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc),
    )
    logger.log(success_record)

    mock_client.table.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/backend/test_failure_logger.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement `FailureLogger`**

```python
# src/backend/logging/failure_logger.py
from src.backend.models.failure import FailureRecord
from src.backend.db.client import get_supabase_client  # adjust to your db client import path


class FailureLogger:
    """Persists failure events to the Supabase failure_logs table.

    Only inserts when record.failed is True; callers may pass any record
    without guarding — no-op on success.
    """

    def log(self, record: FailureRecord) -> None:
        if not record.failed:
            return

        client = get_supabase_client()
        client.table("failure_logs").insert(
            {
                "step": record.step,
                "failed_reason": record.failed_reason,
                "job_url": record.job_url,
                "created_at": record.timestamp.isoformat(),
            }
        ).execute()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/backend/test_failure_logger.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backend/logging/failure_logger.py tests/backend/test_failure_logger.py
git commit -m "feat: add FailureLogger for persisting failures to Supabase"
```

---

## Task 5: Wire `FailureLogger` into the pipeline

**Files:**
- Modify: `src/backend/crew.py` (adjust path if the crew lives elsewhere)

- [ ] **Step 1: Locate where agent outputs are consumed**

```bash
grep -rn "SequentialProcess\|Crew\|kickoff" src/backend/
```

Open the file returned and identify where each agent step produces an output.

- [ ] **Step 2: Import `FailureLogger` and `FailureRecord`**

```python
from datetime import datetime, timezone
from src.backend.logging.failure_logger import FailureLogger
from src.backend.models.failure import FailureRecord

_failure_logger = FailureLogger()
```

- [ ] **Step 3: Call `_failure_logger.log(...)` inline after each step**

After every agent step that returns an output model, add the following pattern. Replace `"<step_name>"` with the actual step identifier (e.g. `"resume_parser"`, `"job_searcher"`, `"form_filler"`):

```python
output = some_agent.run(inputs)

_failure_logger.log(
    FailureRecord(
        step="<step_name>",
        failed=output.failed,
        failed_reason=output.failed_reason,
        job_url=current_job_url,
        timestamp=datetime.now(tz=timezone.utc),
    )
)

if output.failed:
    # existing early-exit or retry logic
    break
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: no regressions; all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/backend/crew.py  # or whichever file was modified
git commit -m "feat: wire FailureLogger inline into pipeline after each step"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** `failed: bool`, `failed_reason: str | None` on all output models; inline logging on failure; Supabase persistence; no dedicated tracking agent — all covered.
- [x] **Placeholder scan:** No TBD, TODO, or vague "add error handling" steps. Every step includes code.
- [x] **Type consistency:** `FailureRecord` defined in Task 1, imported in Tasks 4 and 5. Fields `failed` / `failed_reason` / `step` / `job_url` / `timestamp` used uniformly across all tasks.
