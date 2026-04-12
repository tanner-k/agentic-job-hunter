from crewai import Agent

from worker.config import build_llm, settings
from worker.tools.cover_letter_context_loader import cover_letter_context_loader_tool
from worker.tools.cover_letter_renderer import pdf_renderer_tool
from worker.tools.resume_loader import resume_loader_tool


def build_cover_letter_writer() -> Agent:
    """Build the Cover Letter Writer agent."""
    llm = build_llm(settings.reasoning_model)
    return Agent(
        role="Cover Letter Writer",
        goal=(
            "Draft a tailored, compelling cover letter for each job application that requires one."
        ),
        backstory=(
            "You read the applicant's resume and personal background context, then craft a "
            "personalized cover letter for the specific job. You always assign cover_letter_text "
            "before calling the PDF renderer. If PDF rendering fails (result starts with 'Error:'), "
            "you set cover_letter_path to null but keep cover_letter_text populated."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[resume_loader_tool, cover_letter_context_loader_tool, pdf_renderer_tool],
        llm=llm,
    )
