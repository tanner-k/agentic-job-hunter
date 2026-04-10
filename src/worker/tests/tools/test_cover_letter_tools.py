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


# ── PDF Renderer ──────────────────────────────────────────────────────────────


def test_pdf_renderer_sanitizes_filename(tmp_path):
    """Company and job title are sanitized to lowercase_with_underscores."""
    from pathlib import Path

    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="Acme Corp!",
            job_title="Senior Engineer",
            cover_letter_text="Dear Hiring Manager,",
        )

    assert result.startswith(str(tmp_path))
    filename = Path(result).name
    assert filename.startswith("acme_corp_senior_engineer_")
    assert filename.endswith(".pdf")


def test_pdf_renderer_empty_company_uses_fallback(tmp_path):
    """Empty company string after sanitization falls back to 'unknown_company'."""
    from pathlib import Path

    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="@#$%", job_title="Engineer", cover_letter_text="Hello."
        )

    assert not result.startswith("Error:")
    assert "unknown_company" in Path(result).name


def test_pdf_renderer_empty_job_title_uses_fallback(tmp_path):
    """Empty job title after sanitization falls back to 'unknown_role'."""
    from pathlib import Path

    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="Acme", job_title="---", cover_letter_text="Hello."
        )

    assert not result.startswith("Error:")
    assert "unknown_role" in Path(result).name


def test_pdf_renderer_creates_output_dir(tmp_path):
    """Creates the output directory if it does not exist."""
    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    new_dir = tmp_path / "letters" / "nested"
    assert not new_dir.exists()

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = new_dir
        result = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Hello."
        )

    assert new_dir.exists()
    assert not result.startswith("Error:")


def test_pdf_renderer_two_calls_produce_different_filenames(tmp_path):
    """Timestamp suffix ensures two calls don't overwrite each other."""
    import time
    from pathlib import Path

    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result1 = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Letter 1."
        )
        time.sleep(1.1)  # ensure different second
        result2 = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Letter 2."
        )

    assert result1 != result2
    assert Path(result1).exists()
    assert Path(result2).exists()


def test_pdf_renderer_returns_absolute_path(tmp_path):
    """Returned path is absolute (resolve() applied)."""
    from pathlib import Path

    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = tmp_path
        result = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Hello."
        )

    assert Path(result).is_absolute()
    assert Path(result).exists()


def test_pdf_renderer_returns_error_string_on_bad_path():
    """Returns 'Error: ...' when the output path is unwritable."""
    from pathlib import Path

    from worker.tools.cover_letter_renderer import pdf_renderer_tool

    unwritable = Path("/root/no_permission_here")

    with patch("worker.tools.cover_letter_renderer.settings") as mock_settings:
        mock_settings.cover_letter_output_dir = unwritable
        result = pdf_renderer_tool.run(
            company="Acme", job_title="Engineer", cover_letter_text="Hello."
        )

    assert result.startswith("Error:")
