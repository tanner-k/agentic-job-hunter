"""Tests for retry/error recovery functions in repository.py."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from worker.db import repository


@pytest.fixture()
def mock_client(mocker: MockerFixture) -> MagicMock:
    client = MagicMock()
    mocker.patch("worker.db.repository.get_client", return_value=client)
    return client


class TestFetchFailedApplications:
    def test_filters_by_status_and_max_retries(self, mock_client: MagicMock):
        mock_client.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "app-1"}]
        )

        result = repository.fetch_failed_applications(max_retries=3)

        assert result == [{"id": "app-1"}]
        mock_client.table.assert_called_with("applications")
        mock_client.table.return_value.select.return_value.eq.assert_called_with(
            "status", "failed"
        )
        mock_client.table.return_value.select.return_value.eq.return_value.lt.assert_called_with(
            "retry_count", 3
        )

    def test_returns_empty_list_when_data_is_none(self, mock_client: MagicMock):
        mock_client.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.execute.return_value = MagicMock(
            data=None
        )

        result = repository.fetch_failed_applications()

        assert result == []

    def test_uses_default_max_retries_of_3(self, mock_client: MagicMock):
        mock_client.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        repository.fetch_failed_applications()

        mock_client.table.return_value.select.return_value.eq.return_value.lt.assert_called_with(
            "retry_count", 3
        )


class TestIncrementRetryCount:
    def test_fetches_current_count_then_updates(self, mock_client: MagicMock):
        # First call: select to get current retry_count
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"retry_count": 1}]
        )

        repository.increment_retry_count("app-abc")

        mock_client.table.return_value.update.assert_called_with({"retry_count": 2})
        mock_client.table.return_value.update.return_value.eq.assert_called_with(
            "id", "app-abc"
        )

    def test_handles_missing_row_gracefully(self, mock_client: MagicMock):
        """If the row no longer exists, defaults current count to 0."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        repository.increment_retry_count("app-missing")

        mock_client.table.return_value.update.assert_called_with({"retry_count": 1})
