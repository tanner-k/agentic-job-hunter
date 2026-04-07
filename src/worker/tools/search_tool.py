import multiprocessing
import threading
import time

from crewai.tools import tool

from worker.logging_config import get_logger

logger = get_logger(__name__)

_SEARCH_TIMEOUT = 15  # seconds — hard kill on the subprocess if DDG hangs
_RATE_LIMIT_SLEEP = 3  # seconds between calls

# Ensures parallel LLM tool-calls execute one at a time
_search_lock = threading.Lock()


def _search_worker(query: str, result_queue: multiprocessing.Queue) -> None:
    """Runs inside a child process so it can be hard-killed on timeout."""
    try:
        from ddgs import DDGS  # imported inside worker to avoid pickling issues

        d = DDGS(timeout=10)
        results = list(d.text(query, max_results=6))
        result_queue.put(results)
    except Exception as exc:
        result_queue.put({"error": str(exc)})


@tool("Web Search Tool")
def search_tool(query: str) -> str:
    """Searches the web for open job listings. Returns results with title, URL, and snippet.
    Calls execute sequentially — one at a time — with a hard timeout per query."""
    with _search_lock:
        time.sleep(_RATE_LIMIT_SLEEP)
        logger.info("search_start", query=query)

        q: multiprocessing.Queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_search_worker, args=(query, q), daemon=True
        )
        proc.start()
        proc.join(timeout=_SEARCH_TIMEOUT)

        if proc.is_alive():
            proc.terminate()
            proc.join()
            logger.warning("search_timeout", query=query)
            return "Search timed out — skipping this query."

        raw = q.get_nowait() if not q.empty() else []

        if isinstance(raw, dict) and "error" in raw:
            logger.warning("search_failed", query=query, error=raw["error"])
            return f"Search failed: {raw['error']}"

        results: list[dict] = raw  # type: ignore[assignment]

    if not results:
        return "No results found."

    lines = []
    for r in results:
        lines.append(f"Title: {r.get('title', '')}")
        lines.append(f"URL: {r.get('href', '')}")
        lines.append(f"Snippet: {r.get('body', '')}")
        lines.append("")
    return "\n".join(lines)
