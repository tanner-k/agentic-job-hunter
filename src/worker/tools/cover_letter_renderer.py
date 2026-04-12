import re
from datetime import datetime

from crewai.tools import tool
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate

from worker.config import settings
from worker.logging_config import get_logger

logger = get_logger(__name__)


def _sanitize(text: str, fallback: str) -> str:
    """Lowercase, strip non-alphanumeric-or-space chars, replace spaces with underscores."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", text).strip()
    cleaned = re.sub(r"\s+", "_", cleaned).lower()
    return cleaned if cleaned else fallback


@tool("Cover Letter PDF Renderer")
def pdf_renderer_tool(company: str, job_title: str, cover_letter_text: str) -> str:
    """Render a cover letter to a PDF file and return its absolute path.

    Returns the absolute path string on success, or 'Error: ...' on any failure.
    """
    try:
        safe_company = _sanitize(company, "unknown_company")
        safe_title = _sanitize(job_title, "unknown_role")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_company}_{safe_title}_{timestamp}.pdf"

        output_dir = settings.cover_letter_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / filename).resolve()

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=inch,
            rightMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        story = []
        for line in cover_letter_text.split("\n"):
            story.append(
                Paragraph(line if line.strip() else "&nbsp;", styles["Normal"])
            )
        doc.build(story)

        logger.info("cover_letter_rendered", path=str(output_path))
        return str(output_path)

    except Exception as exc:
        logger.error("cover_letter_render_failed", error=str(exc))
        return f"Error: {exc}"
