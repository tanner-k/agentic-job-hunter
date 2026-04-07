from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ApplicationResult:
    """Immutable result of a single job application attempt."""

    job_url: str
    company: str
    job_title: str
    status: str  # "applied" | "failed" | "skipped"
    search_task_id: str | None = None
    requires_resume: bool = False
    error_message: str | None = None
    applied_at: datetime = None

    def __post_init__(self) -> None:
        # Use object.__setattr__ because dataclass is frozen
        if self.applied_at is None:
            object.__setattr__(self, "applied_at", datetime.now(tz=UTC))
