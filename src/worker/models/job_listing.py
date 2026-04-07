from pydantic import BaseModel


class JobListing(BaseModel):
    """A single job listing returned by the Searcher agent."""

    url: str
    company: str
    job_title: str


class SearchResults(BaseModel):
    """All job listings found by the Searcher agent."""

    jobs: list[JobListing]
