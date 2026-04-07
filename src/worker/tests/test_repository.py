"""Tests for the database repository layer using mocked Supabase client."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from worker.db import repository
from worker.models.application_result import ApplicationResult


@pytest.fixture()
def mock_client(mocker: MockerFixture) -> MagicMock:
    """Return a mock Supabase client injected into the repository module."""
    client = MagicMock()
    mocker.patch("worker.db.repository.get_client", return_value=client)
    return client


class TestUpdateTaskStatus:
    def test_calls_update_with_correct_status(self, mock_client: MagicMock) -> None:
        repository.update_task_status(task_id="task-123", status="running")

        mock_client.table.assert_called_once_with("search_tasks")
        mock_client.table().update.assert_called_once_with({"status": "running"})
        mock_client.table().update().eq.assert_called_once_with("id", "task-123")
        mock_client.table().update().eq().execute.assert_called_once()

    def test_calls_update_with_completed_status(self, mock_client: MagicMock) -> None:
        repository.update_task_status(task_id="task-456", status="completed")

        mock_client.table().update.assert_called_once_with({"status": "completed"})
        mock_client.table().update().eq.assert_called_once_with("id", "task-456")


class TestInsertApplication:
    def test_calls_insert_with_all_required_fields(
        self, mock_client: MagicMock
    ) -> None:
        ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        result = ApplicationResult(
            job_url="https://jobs.example.com/123",
            company="Acme Corp",
            job_title="Software Engineer",
            status="applied",
            search_task_id="task-abc",
            requires_resume=True,
            error_message=None,
            applied_at=ts,
        )

        repository.insert_application(result)

        mock_client.table.assert_called_once_with("applications")
        mock_client.table().insert.assert_called_once_with(
            {
                "search_task_id": "task-abc",
                "company": "Acme Corp",
                "job_title": "Software Engineer",
                "job_url": "https://jobs.example.com/123",
                "status": "applied",
                "requires_resume": True,
                "applied_at": ts.isoformat(),
                "error_message": None,
            }
        )
        mock_client.table().insert().execute.assert_called_once()

    def test_calls_insert_with_failed_status(self, mock_client: MagicMock) -> None:
        ts = datetime(2025, 6, 15, 11, 0, 0, tzinfo=UTC)
        result = ApplicationResult(
            job_url="https://jobs.example.com/456",
            company="Globex",
            job_title="Data Engineer",
            status="failed",
            error_message="Form submission timed out",
            applied_at=ts,
        )

        repository.insert_application(result)

        call_args = mock_client.table().insert.call_args[0][0]
        assert call_args["status"] == "failed"
        assert call_args["error_message"] == "Form submission timed out"
        assert call_args["search_task_id"] is None


class TestFetchPendingTasks:
    def test_returns_data_from_response(self, mock_client: MagicMock) -> None:
        expected = [
            {"id": "task-1", "status": "pending"},
            {"id": "task-2", "status": "pending"},
        ]
        mock_client.table().select().eq().execute.return_value = MagicMock(
            data=expected
        )

        result = repository.fetch_pending_tasks()

        assert result == expected
        mock_client.table.assert_called_with("search_tasks")
        mock_client.table().select.assert_called_with("*")
        mock_client.table().select().eq.assert_called_with("status", "pending")

    def test_returns_empty_list_when_data_is_none(self, mock_client: MagicMock) -> None:
        mock_client.table().select().eq().execute.return_value = MagicMock(data=None)

        result = repository.fetch_pending_tasks()

        assert result == []
