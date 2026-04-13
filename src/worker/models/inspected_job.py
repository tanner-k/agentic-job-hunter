from pydantic import BaseModel


class InspectedJob(BaseModel):
    """A job listing enriched with form fields extracted from its application page."""

    url: str
    company: str
    job_title: str
    form_fields: list[str]  # exact labels extracted from the rendered DOM
    requires_resume: bool  # True if a non-cover-letter <input type="file"> was found
    requires_cover_letter: bool  # True if a cover-letter-labeled field was found
    job_description: str  # visible page text, trimmed to 4000 chars
    failed: bool = False
    """True if this agent step failed."""
    failed_reason: str | None = None
    """Human-readable description of the failure. Must be set when failed=True."""


class InspectedJobs(BaseModel):
    """All inspected jobs produced by the Field Inspector agent."""

    jobs: list[InspectedJob]
    failed: bool = False
    """True if this agent step failed."""
    failed_reason: str | None = None
    """Human-readable description of the failure. Must be set when failed=True."""
