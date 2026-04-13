from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from worker.models.failure import FailureRecord


def test_failure_record_required_fields():
    record = FailureRecord(
        step="resume_parser",
        failed=True,
        failed_reason="LLM returned empty response after 3 retries",
        job_url="https://example.com/jobs/123",
        timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC),
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
            timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC),
        )


def test_failure_record_reason_none_allowed_when_not_failed():
    record = FailureRecord(
        step="resume_parser",
        failed=False,
        failed_reason=None,
        job_url="https://example.com/jobs/123",
        timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC),
    )
    assert record.failed_reason is None


def test_failure_record_is_immutable():
    record = FailureRecord(
        step="resume_parser",
        failed=True,
        failed_reason="timeout",
        job_url="https://example.com/jobs/123",
        timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(ValidationError):
        record.step = "other_step"  # type: ignore
