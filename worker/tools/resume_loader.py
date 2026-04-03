import pdfplumber
from crewai.tools import tool

from worker.config import settings
from worker.logging_config import get_logger

logger = get_logger(__name__)


@tool("Resume Loader")
def resume_loader_tool() -> str:
    """Loads and returns the text content of the user's resume PDF for job evaluation."""
    path = settings.resume_path
    if not path.exists():
        logger.error("resume_not_found", path=str(path))
        return f"Error: Resume not found at {path}. Place your resume.pdf at {path}"

    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages).strip()
    logger.info("resume_loaded", chars=len(text), pages=len(pages))
    return text
