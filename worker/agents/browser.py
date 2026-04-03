from crewai import Agent, LLM

from worker.config import settings
from worker.tools.browser_tool import browser_tool


def build_browser() -> Agent:
    """Build the Automated Browser Executor agent."""
    llm = LLM(model=settings.fast_model, base_url=settings.ollama_base_url)
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
