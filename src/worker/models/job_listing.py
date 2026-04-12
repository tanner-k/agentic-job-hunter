from pydantic import BaseModel


class JobListing(BaseModel):
    """A single job listing returned by the Searcher agent."""

    url: str
    company: str
    job_title: str
    failed: bool = False
    """True if this agent step failed."""
    failed_reason: str | None = None
    """Human-readable description of the failure. Must be set when failed=True."""


class SearchResults(BaseModel):
    """All job listings found by the Searcher agent."""

    jobs: list[JobListing]
    failed: bool = False
    """True if this agent step failed."""
    failed_reason: str | None = None
    """Human-readable description of the failure. Must be set when failed=True."""
