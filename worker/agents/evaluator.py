from crewai import Agent, LLM

from worker.config import settings
from worker.tools.resume_loader import resume_loader_tool


def build_evaluator() -> Agent:
    """Build the Senior Application Strategist agent."""
    llm = LLM(model=settings.reasoning_model, base_url=settings.ollama_base_url)
    return Agent(
        role="Senior Application Strategist",
        goal=(
            "Analyze job listings against the user criteria, generate form-fill instructions, "
            "and trigger resume uploads."
        ),
        backstory=(
            "You evaluate if a job meets the minimum salary and keyword requirements. "
            "If it passes, you create a JSON-like instruction map for the Browser. "
            "You ALWAYS flag if the application requires the user's resume so the Browser knows to upload it."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[resume_loader_tool],
        llm=llm,
    )
