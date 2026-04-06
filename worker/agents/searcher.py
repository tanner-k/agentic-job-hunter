from crewai import Agent

from worker.config import build_llm, settings
from worker.tools.search_tool import search_tool


def build_searcher() -> Agent:
    """Build the Targeted Job Scout agent."""
    llm = build_llm(settings.fast_model)
    return Agent(
        role="Targeted Job Scout",
        goal="Find jobs matching strict location, salary, and keyword criteria.",
        backstory=(
            "You are a precise data gatherer. You strictly adhere to user-provided search parameters. "
            "You construct advanced search queries (using site: operators if a specific website or company "
            "is requested) to find exact matches."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[search_tool],
        llm=llm,
        max_iter=6,
    )
