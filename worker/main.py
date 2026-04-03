"""Agentic Job Hunter — Worker entry point.

Run with: uv run python -m worker.main
"""

import asyncio
import os

from worker.config import settings
from worker.crew import run_crew
from worker.db.repository import fetch_pending_tasks, update_task_status
from worker.logging_config import configure_logging, get_logger
from worker.models.search_criteria import SearchCriteria

# Suppress CrewAI's OpenAI key requirement
os.environ.setdefault("OPENAI_API_KEY", "NA")

configure_logging()
logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 30 * 60  # 30 minutes


def _handle_task(task: dict) -> None:
    """Process a single search task synchronously (CrewAI is sync)."""
    task_id: str = task["id"]
    logger.info("task_started", task_id=task_id, job_title=task.get("job_title"))
    try:
        update_task_status(task_id, "running")
        criteria = SearchCriteria.from_dict(task)
        run_crew(criteria, task_id=task_id)
        update_task_status(task_id, "done")
        logger.info("task_done", task_id=task_id)
    except Exception as exc:
        logger.error("task_failed", task_id=task_id, error=str(exc))
        update_task_status(task_id, "failed")


def _drain_pending_tasks() -> None:
    """Fetch and process all pending tasks until none remain."""
    pending = fetch_pending_tasks()
    if not pending:
        logger.info("no_pending_tasks")
        return
    logger.info("pending_tasks_found", count=len(pending))
    for task in pending:
        _handle_task(task)


async def _poll_loop() -> None:
    """Check for pending tasks on startup, then every 30 minutes."""
    while True:
        _drain_pending_tasks()
        logger.info("poll_sleeping", minutes=POLL_INTERVAL_SECONDS // 60)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _email_loop() -> None:
    """Email monitoring loop — waits first, then runs every 2 hours."""
    while True:
        await asyncio.sleep(settings.email_poll_interval_seconds)
        logger.info("email_agent_tick")
        try:
            from worker.agents import email_agent
            await asyncio.get_event_loop().run_in_executor(None, email_agent.run)
        except Exception as exc:
            logger.error("email_agent_error", error=str(exc))


async def main() -> None:
    logger.info(
        "worker_starting",
        fast_model=settings.fast_model,
        reasoning_model=settings.reasoning_model,
        poll_interval_minutes=POLL_INTERVAL_SECONDS // 60,
    )
    await asyncio.gather(
        _poll_loop(),
        _email_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
