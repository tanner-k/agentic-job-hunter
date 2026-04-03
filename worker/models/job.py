from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Job:
    """Immutable representation of a discovered job listing."""

    url: str
    company: str
    title: str
    snippet: str = ""
    match_score: float = 0.0
    form_fields: dict[str, Any] = field(default_factory=dict)
    requires_resume: bool = False
