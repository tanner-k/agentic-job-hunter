from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from worker.logging.failure_logger import FailureLogger
from worker.models.failure import FailureRecord


def _failed_record(
    step: str = "form_filler", reason: str = "selector not found"
) -> FailureRecord:
    return FailureRecord(
        step=step,
        failed=True,
        failed_reason=reason,
        job_url="https://example.com/jobs/42",
        timestamp=datetime(2026, 4, 7, 10, 0, 0, tzinfo=UTC),
    )


@patch("worker.logging.failure_logger.get_client")
def test_log_inserts_failure_record(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value = (
        MagicMock()
    )

    logger = FailureLogger()
    record = _failed_record()
    logger.log(record)

    mock_client.table.assert_called_once_with("failure_logs")
    inserted = mock_client.table.return_value.insert.call_args[0][0]
    assert inserted["step"] == "form_filler"
    assert inserted["failed_reason"] == "selector not found"
    assert inserted["job_url"] == "https://example.com/jobs/42"


@patch("worker.logging.failure_logger.get_client")
def test_log_no_ops_when_not_failed(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    logger = FailureLogger()
    success_record = FailureRecord(
        step="form_filler",
        failed=False,
        failed_reason=None,
        job_url="https://example.com/jobs/42",
        timestamp=datetime(2026, 4, 7, 10, 0, 0, tzinfo=UTC),
    )
    logger.log(success_record)

    mock_client.table.assert_not_called()


@patch("worker.logging.failure_logger.get_client")
def test_log_swallows_insert_exception(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.side_effect = (
        RuntimeError("DB down")
    )

    logger = FailureLogger()
    record = _failed_record()
    # Must not raise
    logger.log(record)
