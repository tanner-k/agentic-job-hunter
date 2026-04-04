from crewai import LLM, Agent

from worker.config import settings
from worker.tools.field_inspector_tool import field_inspector_tool


def build_field_inspector() -> Agent:
    """Build the Form Field Inspector agent.

    Visits each job URL and extracts the exact form field labels from the
    rendered DOM. Uses the fast model since no reasoning is required —
    just sequential tool calls.
    """
    llm = LLM(model=settings.fast_model, base_url=settings.ollama_base_url)
    return Agent(
        role="Form Field Inspector",
        goal="Visit each job URL and return the exact form fields present on the page.",
        backstory=(
            "You are a precise DOM inspector. For each job URL you receive, you call the "
            "Field Inspector tool exactly once and report what fields you found. "
            "You never skip a URL and never call the tool more than once per URL."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[field_inspector_tool],
        llm=llm,
        max_iter=8,
    )
