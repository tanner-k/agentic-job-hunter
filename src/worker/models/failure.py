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
