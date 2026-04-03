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
            "applied_at": result.applied_at.isoformat(),
            "error_message": result.error_message,
        }
    ).execute()
    logger.info("application_inserted", company=result.company, status=result.status)


def fetch_pending_tasks() -> list[dict]:
    """Fetch any tasks that are still pending (fallback on startup)."""
    client = get_client()
    response = client.table("search_tasks").select("*").eq("status", "pending").execute()
    return response.data or []


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
            "synced_at": log.synced_at.isoformat(),
        }
    ).execute()
    logger.info("email_log_inserted", sender=log.sender, sentiment=log.sentiment)
