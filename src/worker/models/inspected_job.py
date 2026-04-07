from pydantic import BaseModel


class InspectedJob(BaseModel):
    """A job listing enriched with form fields extracted from its application page."""

    url: str
    company: str
    job_title: str
    form_fields: list[str]  # exact labels extracted from the rendered DOM
    requires_resume: bool  # True if <input type="file"> was found on the page


class InspectedJobs(BaseModel):
    """All inspected jobs produced by the Field Inspector agent."""

    jobs: list[InspectedJob]
