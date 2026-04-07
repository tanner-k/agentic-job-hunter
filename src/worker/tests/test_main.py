"""Tests for worker/main.py CLI flags and handler functions."""

from unittest.mock import MagicMock, patch


def test_dry_run_flag_parsed():
    import importlib
    import sys

    # Re-parse with --dry-run in argv
    sys.argv = ["worker.main", "--dry-run"]
    import worker.main as main_module

    importlib.reload(main_module)
    assert main_module._args.dry_run is True
    sys.argv = ["worker.main"]  # reset


def test_retry_failed_flag_parsed():
    import importlib
    import sys

    sys.argv = ["worker.main", "--retry-failed"]
    import worker.main as main_module

    importlib.reload(main_module)
    assert main_module._args.retry_failed is True
    sys.argv = ["worker.main"]  # reset


def test_headless_false_flag_parsed():
    import importlib
    import sys

    sys.argv = ["worker.main", "--headless-false"]
    import worker.main as main_module

    importlib.reload(main_module)
    assert main_module._args.headless_false is True
    sys.argv = ["worker.main"]  # reset


class TestHandleDryRun:
    def test_prints_message_when_no_pending_tasks(self, capsys):
        import worker.main as main_module

        with patch.object(main_module, "fetch_pending_tasks", return_value=[]):
            main_module._handle_dry_run()

        out = capsys.readouterr().out
        assert "No pending tasks" in out

    def test_calls_run_crew_with_dry_run_true(self):
        import worker.main as main_module

        task = {
            "id": "t-1",
            "job_title": "Engineer",
            "location": "Remote",
            "min_salary": 100000,
            "keywords": [],
            "company": None,
            "job_website": None,
        }
        mock_packets = MagicMock()
        mock_packets.job_applications = []
        mock_packets.model_dump.return_value = {}

        with (
            patch.object(main_module, "fetch_pending_tasks", return_value=[task]),
            patch.object(
                main_module, "run_crew", return_value=mock_packets
            ) as mock_run,
        ):
            main_module._handle_dry_run()

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("dry_run") is True

    def test_prints_none_message_when_no_packets(self, capsys):
        import worker.main as main_module

        task = {
            "id": "t-1",
            "job_title": "Engineer",
            "location": "Remote",
            "min_salary": 100000,
            "keywords": [],
            "company": None,
            "job_website": None,
        }

        with (
            patch.object(main_module, "fetch_pending_tasks", return_value=[task]),
            patch.object(main_module, "run_crew", return_value=None),
        ):
            main_module._handle_dry_run()

        out = capsys.readouterr().out
        assert "no packets" in out.lower()


class TestHandleRetryFailed:
    def test_prints_message_when_no_failed_rows(self, capsys):
        import worker.main as main_module

        with patch("worker.db.repository.fetch_failed_applications", return_value=[]):
            main_module._handle_retry_failed()

        out = capsys.readouterr().out
        assert "No failed" in out

    def test_increments_retry_count_for_each_row(self):
        import worker.main as main_module

        rows = [
            {
                "id": "app-1",
                "job_url": "https://jobs.example.com/1",
                "requires_resume": False,
            },
            {
                "id": "app-2",
                "job_url": "https://jobs.example.com/2",
                "requires_resume": True,
            },
        ]

        with (
            patch("worker.db.repository.fetch_failed_applications", return_value=rows),
            patch("worker.db.repository.increment_retry_count") as mock_inc,
            patch("worker.tools.browser_tool.browser_tool", return_value="ok"),
        ):
            main_module._handle_retry_failed()

        assert mock_inc.call_count == 2
