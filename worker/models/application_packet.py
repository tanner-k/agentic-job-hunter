from pydantic import BaseModel


class ApplicationPacket(BaseModel):
    """Instructions for the Browser agent to fill and submit one job application."""

    url: str
    company: str
    job_title: str
    json_instructions: str  # JSON-encoded string: '{"First Name": "Tanner", ...}'
    requires_resume: bool


class ApplicationPackets(BaseModel):
    """All application packets produced by the Evaluator agent."""

    packets: list[ApplicationPacket]
