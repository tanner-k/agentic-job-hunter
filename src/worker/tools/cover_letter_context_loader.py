from crewai.tools import tool

from worker.config import settings
from worker.logging_config import get_logger

logger = get_logger(__name__)


@tool("Cover Letter Context Loader")
def cover_letter_context_loader_tool() -> str:
    """Load the user's cover letter context file (tone, narrative, background).

    Returns the file contents, or an empty string if the file does not exist.
    """
    path = settings.cover_letter_context_path
    if not path.exists():
        logger.warning("cover_letter_context_not_found", path=str(path))
        return ""
    return path.read_text().strip()
