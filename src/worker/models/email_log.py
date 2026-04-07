from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class EmailLog:
    """Immutable record of a processed recruiter email."""

    subject: str
    sender: str
    sentiment: str  # "interest" | "rejection" | "spam"
    summary: str
    received_at: datetime
    draft_link: str | None = None
    synced_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.synced_at is None:
            object.__setattr__(self, "synced_at", datetime.now(tz=UTC))
