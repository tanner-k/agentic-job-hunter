from worker.db.client import get_client
from worker.logging_config import get_logger
from worker.models.application_result import ApplicationResult
from worker.models.email_log import EmailLog

logger = get_logger(__name__)


def update_task_status(task_id: str, status: str) -> None:
    """Update the status of a search_task row."""
    client = get_client()
    client.table("search_tasks").update({"status": status}).eq("id", task_id).execute()
    logger.info("task_status_updated", task_id=task_id, status=status)


def insert_application(result: ApplicationResult) -> None:
    """Insert an application result into the applications table."""
    client = get_client()
    client.table("applications").insert(
        {
            "search_task_id": result.search_task_id,
            "company": result.company,
            "job_title": result.job_title,
            "job_url": result.job_url,
            "status": result.status,
            "requires_resume": result.requires_resume,
            "applied_at": result.applied_at.isoformat(),  # type: ignore[union-attr]
            "error_message": result.error_message,
        }
    ).execute()
    logger.info("application_inserted", company=result.company, status=result.status)


def fetch_pending_tasks() -> list[dict]:
    """Fetch any tasks that are still pending (fallback on startup)."""
    client = get_client()
    response = (
        client.table("search_tasks").select("*").eq("status", "pending").execute()
    )
    return response.data or []  # type: ignore[return-value]


def fetch_failed_applications(max_retries: int = 3) -> list[dict]:
    """Fetch failed applications that are still under the retry limit."""
    client = get_client()
    response = (
        client.table("applications")
        .select("*")
        .eq("status", "failed")
        .lt("retry_count", max_retries)
        .order("applied_at")
        .execute()
    )
    return response.data or []  # type: ignore[return-value]


def increment_retry_count(application_id: str) -> None:
    """Increment the retry_count of an application row by 1."""
    client = get_client()
    response = (
        client.table("applications")
        .select("retry_count")
        .eq("id", application_id)
        .execute()
    )
    rows: list[dict] = response.data or []  # type: ignore[assignment]
    current = rows[0]["retry_count"] if rows else 0
    client.table("applications").update({"retry_count": current + 1}).eq(
        "id", application_id
    ).execute()
    logger.info(
        "retry_count_incremented", application_id=application_id, new_count=current + 1
    )


def insert_email_log(log: EmailLog) -> None:
    """Insert a processed email record into email_logs."""
    client = get_client()
    client.table("email_logs").insert(
        {
            "subject": log.subject,
            "sender": log.sender,
            "sentiment": log.sentiment,
            "summary": log.summary,
            "draft_link": log.draft_link,
            "received_at": log.received_at.isoformat(),
            "synced_at": log.synced_at.isoformat(),  # type: ignore[union-attr]
        }
    ).execute()
    logger.info("email_log_inserted", sender=log.sender, sentiment=log.sentiment)
