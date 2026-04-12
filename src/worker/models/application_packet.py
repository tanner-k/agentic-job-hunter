from pydantic import BaseModel


class ApplicationPacket(BaseModel):
    """Instructions for the Browser agent to fill and submit one job application."""

    url: str
    company: str
    job_title: str
    json_instructions: str  # JSON-encoded string: '{"First Name": "Tanner", ...}'
    requires_resume: bool
    cover_letter_text: str | None = None  # plain text for cover letter text fields
    cover_letter_path: str | None = None  # absolute path to rendered PDF


class ApplicationPackets(BaseModel):
    """All application packets produced by the Evaluator agent."""

    job_applications: list[ApplicationPacket]
