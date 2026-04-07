from crewai import Agent

from worker.config import build_llm, settings
from worker.tools.browser_tool import browser_tool


def build_browser() -> Agent:
    """Build the Automated Browser Executor agent."""
    llm = build_llm(settings.fast_model)
    return Agent(
        role="Automated Browser Executor",
        goal="Execute form instructions and handle local file uploads.",
        backstory=(
            "You are an execution engine. You take the URL, the field instructions, "
            "and the resume requirement flag from the Evaluator, and you process the application flawlessly."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[browser_tool],
        llm=llm,
        max_iter=5,
    )
