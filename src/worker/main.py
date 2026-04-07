"""Agentic Job Hunter — Worker entry point.

Run with: uv run python -m worker.main
         uv run python -m worker.main --headless-false
         uv run python -m worker.main --dry-run
         uv run python -m worker.main --retry-failed
"""

import argparse
import asyncio
import os

# Parse args before importing settings so we can mutate settings.headless early.
_parser = argparse.ArgumentParser(description="Agentic Job Hunter worker")
_parser.add_argument(
    "--headless-false",
    action="store_true",
    dest="headless_false",
    help="Run Playwright browser in non-headless (visible) mode",
)
_parser.add_argument(
    "--dry-run",
    action="store_true",
    dest="dry_run",
    help="Preview ApplicationPackets for the first pending task without submitting",
)
_parser.add_argument(
    "--retry-failed",
    action="store_true",
    dest="retry_failed",
    help="Re-attempt failed application rows that are under the retry limit",
)
_args, _ = _parser.parse_known_args()


from worker.config import settings  # noqa: E402
from worker.crew import run_crew  # noqa: E402
from worker.db.repository import (  # noqa: E402
    fetch_pending_tasks,
    update_task_status,
)
from worker.logging_config import configure_logging, get_logger  # noqa: E402
from worker.models.search_criteria import SearchCriteria  # noqa: E402

# Suppress CrewAI's OpenAI key requirement
os.environ.setdefault("OPENAI_API_KEY", "NA")

if _args.headless_false:
    settings.headless = False

configure_logging()
logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 30 * 60  # 30 minutes
APPLICATIONS_PER_TASK = 10


def _handle_task(task: dict) -> None:
    """Run up to APPLICATIONS_PER_TASK single-job crew cycles for one search task.

    Each cycle finds and applies to the single best matching job, then adds
    that company to an exclusion list so the next cycle targets a different company.
    """
    task_id: str = task["id"]
    logger.info("task_started", task_id=task_id, job_title=task.get("job_title"))
    update_task_status(task_id, "running")

    criteria = SearchCriteria.from_dict(task)
    excluded_companies: list[str] = []
    applications_attempted = 0

    for round_num in range(1, APPLICATIONS_PER_TASK + 1):
        logger.info(
            "application_round_start",
            task_id=task_id,
            round=round_num,
            excluded=excluded_companies,
        )
        try:
            company = run_crew(
                criteria,
                task_id=task_id,
                excluded_companies=excluded_companies,
            )
            applications_attempted += 1
            if company:
                excluded_companies.append(company)
        except Exception as exc:
            logger.error(
                "application_round_failed",
                task_id=task_id,
                round=round_num,
                error=str(exc),
            )

    update_task_status(task_id, "done")
    logger.info(
        "task_done",
        task_id=task_id,
        applications_attempted=applications_attempted,
    )


def _drain_pending_tasks() -> None:
    """Fetch and process all pending tasks until none remain."""
    pending = fetch_pending_tasks()
    if not pending:
        logger.info("no_pending_tasks")
        return
    logger.info("pending_tasks_found", count=len(pending))
    for task in pending:
        _handle_task(task)


def _handle_dry_run() -> None:
    """Preview ApplicationPackets for the first pending task without submitting.

    Runs Searcher → Field Inspector → Evaluator but skips the Browser agent.
    Prints the resulting ApplicationPackets as formatted JSON and exits.
    """
    pending = fetch_pending_tasks()
    if not pending:
        logger.info("no_pending_tasks_for_dry_run")
        print("No pending tasks found.")
        return

    task = pending[0]
    criteria = SearchCriteria.from_dict(task)
    logger.info("dry_run_starting", task_id=task["id"], job_title=criteria.job_title)

    packets = run_crew(criteria, task_id=task["id"], dry_run=True)
    if packets is None:
        print("Dry run produced no packets (no matching jobs found).")
        return

    import json  # already imported at module level; local import keeps this self-contained

    print(json.dumps(packets.model_dump(), indent=2))
    logger.info("dry_run_complete", job_count=len(packets.job_applications))


def _handle_retry_failed() -> None:
    """Re-attempt failed application rows that are still under the retry limit.

    Calls browser_tool directly for each row — skips the full LLM crew.
    Increments retry_count on each attempt regardless of outcome.
    """
    from worker.db.repository import fetch_failed_applications, increment_retry_count
    from worker.tools.browser_tool import browser_tool

    rows = fetch_failed_applications()
    if not rows:
        logger.info("no_failed_applications_to_retry")
        print("No failed applications eligible for retry.")
        return

    logger.info("retrying_failed_applications", count=len(rows))
    for row in rows:
        app_id: str = row["id"]
        url: str = row.get("job_url", "")
        requires_resume: bool = row.get("requires_resume", False)
        logger.info("retrying_application", application_id=app_id, url=url)
        try:
            result = browser_tool(
                url=url,
                json_instructions="{}",
                requires_resume=requires_resume,
            )
            logger.info("retry_result", application_id=app_id, result=result[:100])
        except Exception as exc:
            logger.error("retry_error", application_id=app_id, error=str(exc))
        finally:
            increment_retry_count(app_id)

    print(f"Retry complete. Attempted {len(rows)} application(s).")


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
    if _args.dry_run:
        _handle_dry_run()
        return

    if _args.retry_failed:
        _handle_retry_failed()
        return

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
