from langchain_community.tools import DuckDuckGoSearchRun
from crewai.tools import tool

_ddg = DuckDuckGoSearchRun()


@tool("Web Search Tool")
def search_tool(query: str) -> str:
    """Searches the web for open job listings, company information, and application requirements."""
    return _ddg.invoke(query)
