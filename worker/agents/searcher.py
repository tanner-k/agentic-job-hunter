from crewai import LLM, Agent

from worker.config import settings
from worker.tools.search_tool import search_tool


def build_searcher() -> Agent:
    """Build the Targeted Job Scout agent."""
    llm = LLM(model=settings.fast_model, base_url=settings.ollama_base_url)
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
