"""Tests for cover letter tools: context loader and PDF renderer."""

from unittest.mock import patch

# ── Context Loader ────────────────────────────────────────────────────────────


def test_context_loader_returns_empty_string_when_file_missing(tmp_path):
    """Returns '' and logs a warning when the context file does not exist."""
    from worker.tools.cover_letter_context_loader import (
        cover_letter_context_loader_tool,
    )

    missing_path = tmp_path / "cover_letter_context.md"

    with patch("worker.tools.cover_letter_context_loader.settings") as mock_settings:
        mock_settings.cover_letter_context_path = missing_path
        result = cover_letter_context_loader_tool.run()

    assert result == ""


def test_context_loader_returns_empty_string_for_empty_file(tmp_path):
    """Returns '' for a file that exists but has no content."""
    from worker.tools.cover_letter_context_loader import (
        cover_letter_context_loader_tool,
    )

    empty_file = tmp_path / "cover_letter_context.md"
    empty_file.write_text("")

    with patch("worker.tools.cover_letter_context_loader.settings") as mock_settings:
        mock_settings.cover_letter_context_path = empty_file
        result = cover_letter_context_loader_tool.run()

    assert result == ""


def test_context_loader_returns_file_content(tmp_path):
    """Returns the file contents when the file exists and has content."""
    from worker.tools.cover_letter_context_loader import (
        cover_letter_context_loader_tool,
    )

    context_file = tmp_path / "cover_letter_context.md"
    context_file.write_text("I am passionate about distributed systems and Python.")

    with patch("worker.tools.cover_letter_context_loader.settings") as mock_settings:
        mock_settings.cover_letter_context_path = context_file
        result = cover_letter_context_loader_tool.run()

    assert result == "I am passionate about distributed systems and Python."
