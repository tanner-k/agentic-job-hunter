from worker.db.client import get_client
from worker.logging_config import get_logger
from worker.models.failure import FailureRecord

_logger = get_logger(__name__)


class FailureLogger:
    """Persists failure events to the Supabase failure_logs table.

    Only inserts when record.failed is True; callers may pass any record
    without guarding — no-op on success. Insert failures are logged but
    never propagated so that logging never crashes the pipeline.
    """

    def log(self, record: FailureRecord) -> None:
        """Log a failure record to the database.

        Args:
            record: The failure record to log. If record.failed is False, this is a no-op.
        """
        if not record.failed:
            return

        try:
            client = get_client()
            client.table("failure_logs").insert(
                {
                    "step": record.step,
                    "failed_reason": record.failed_reason,
                    "job_url": record.job_url,
                    "created_at": record.timestamp.isoformat(),
                }
            ).execute()
        except Exception:
            _logger.exception(
                "failure_log_insert_failed",
                step=record.step,
                job_url=record.job_url,
            )
